#!/usr/bin/env python
import sys
import os
sys.path.append(os.path.normpath(os.path.join(os.path.dirname(__file__), '../lib')))
import init
import config
import misc
from brixcoind import BrixcoinDaemon
from models import Superblock, Proposal, GovernanceObject
from models import VoteSignals, VoteOutcomes, Transient
import socket
from misc import printdbg
import time
from bitcoinrpc.authproxy import JSONRPCException
import signal
import atexit
import random
from scheduler import Scheduler
import argparse


# sync brixcoind gobject list with our local relational DB backend
def perform_brixcoind_object_sync(brixcoind):
    GovernanceObject.sync(brixcoind)


def prune_expired_proposals(brixcoind):
    # vote delete for old proposals
    for proposal in Proposal.expired(brixcoind.superblockcycle()):
        proposal.vote(brixcoind, VoteSignals.delete, VoteOutcomes.yes)


# ping brixcoind
def sentinel_ping(brixcoind):
    printdbg("in sentinel_ping")

    brixcoind.ping()

    printdbg("leaving sentinel_ping")


def attempt_superblock_creation(brixcoind):
    import brixcoinlib

    if not brixcoind.is_masternode():
        print("We are not a Masternode... can't submit superblocks!")
        return

    # query votes for this specific ebh... if we have voted for this specific
    # ebh, then it's voted on. since we track votes this is all done using joins
    # against the votes table
    #
    # has this masternode voted on *any* superblocks at the given event_block_height?
    # have we voted FUNDING=YES for a superblock for this specific event_block_height?

    event_block_height = brixcoind.next_superblock_height()

    if Superblock.is_voted_funding(event_block_height):
        # printdbg("ALREADY VOTED! 'til next time!")

        # vote down any new SBs because we've already chosen a winner
        for sb in Superblock.at_height(event_block_height):
            if not sb.voted_on(signal=VoteSignals.funding):
                sb.vote(brixcoind, VoteSignals.funding, VoteOutcomes.no)

        # now return, we're done
        return

    if not brixcoind.is_govobj_maturity_phase():
        printdbg("Not in maturity phase yet -- will not attempt Superblock")
        return

    proposals = Proposal.approved_and_ranked(proposal_quorum=brixcoind.governance_quorum(), next_superblock_max_budget=brixcoind.next_superblock_max_budget())
    budget_max = brixcoind.get_superblock_budget_allocation(event_block_height)
    sb_epoch_time = brixcoind.block_height_to_epoch(event_block_height)

    maxgovobjdatasize = brixcoind.govinfo['maxgovobjdatasize']
    sb = brixcoinlib.create_superblock(proposals, event_block_height, budget_max, sb_epoch_time, maxgovobjdatasize)
    if not sb:
        printdbg("No superblock created, sorry. Returning.")
        return

    # find the deterministic SB w/highest object_hash in the DB
    dbrec = Superblock.find_highest_deterministic(sb.hex_hash())
    if dbrec:
        dbrec.vote(brixcoind, VoteSignals.funding, VoteOutcomes.yes)

        # any other blocks which match the sb_hash are duplicates, delete them
        for sb in Superblock.select().where(Superblock.sb_hash == sb.hex_hash()):
            if not sb.voted_on(signal=VoteSignals.funding):
                sb.vote(brixcoind, VoteSignals.delete, VoteOutcomes.yes)

        printdbg("VOTED FUNDING FOR SB! We're done here 'til next superblock cycle.")
        return
    else:
        printdbg("The correct superblock wasn't found on the network...")

    # if we are the elected masternode...
    if (brixcoind.we_are_the_winner()):
        printdbg("we are the winner! Submit SB to network")
        sb.submit(brixcoind)


def check_object_validity(brixcoind):
    # vote (in)valid objects
    for gov_class in [Proposal, Superblock]:
        for obj in gov_class.select():
            obj.vote_validity(brixcoind)


def is_brixcoind_port_open(brixcoind):
    # test socket open before beginning, display instructive message to MN
    # operators if it's not
    port_open = False
    try:
        info = brixcoind.rpc_command('getgovernanceinfo')
        port_open = True
    except (socket.error, JSONRPCException) as e:
        print("%s" % e)

    return port_open


def main():
    brixcoind = BrixcoinDaemon.from_brixcoin_conf(config.brixcoin_conf)
    options = process_args()

    # check brixcoind connectivity
    if not is_brixcoind_port_open(brixcoind):
        print("Cannot connect to brixcoind. Please ensure brixcoind is running and the JSONRPC port is open to Sentinel.")
        return

    # check brixcoind sync
    if not brixcoind.is_synced():
        print("brixcoind not synced with network! Awaiting full sync before running Sentinel.")
        return

    # ensure valid masternode
    if not brixcoind.is_masternode():
        print("Invalid Masternode Status, cannot continue.")
        return

    # register a handler if SENTINEL_DEBUG is set
    if os.environ.get('SENTINEL_DEBUG', None):
        import logging
        logger = logging.getLogger('peewee')
        logger.setLevel(logging.DEBUG)
        logger.addHandler(logging.StreamHandler())

    if options.bypass:
        # bypassing scheduler, remove the scheduled event
        printdbg("--bypass-schedule option used, clearing schedule")
        Scheduler.clear_schedule()

    if not Scheduler.is_run_time():
        printdbg("Not yet time for an object sync/vote, moving on.")
        return

    if not options.bypass:
        # delay to account for cron minute sync
        Scheduler.delay()

    # running now, so remove the scheduled event
    Scheduler.clear_schedule()

    # ========================================================================
    # general flow:
    # ========================================================================
    #
    # load "gobject list" rpc command data, sync objects into internal database
    perform_brixcoind_object_sync(brixcoind)

    if brixcoind.has_sentinel_ping:
        sentinel_ping(brixcoind)

    # auto vote network objects as valid/invalid
    # check_object_validity(brixcoind)

    # vote to delete expired proposals
    prune_expired_proposals(brixcoind)

    # create a Superblock if necessary
    attempt_superblock_creation(brixcoind)

    # schedule the next run
    Scheduler.schedule_next_run()


def signal_handler(signum, frame):
    print("Got a signal [%d], cleaning up..." % (signum))
    Transient.delete('SENTINEL_RUNNING')
    sys.exit(1)


def cleanup():
    Transient.delete(mutex_key)


def process_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-b', '--bypass-scheduler',
                        action='store_true',
                        help='Bypass scheduler and sync/vote immediately',
                        dest='bypass')
    args = parser.parse_args()

    return args


if __name__ == '__main__':
    atexit.register(cleanup)
    signal.signal(signal.SIGINT, signal_handler)

    # ensure another instance of Sentinel is not currently running
    mutex_key = 'SENTINEL_RUNNING'
    # assume that all processes expire after 'timeout_seconds' seconds
    timeout_seconds = 90

    is_running = Transient.get(mutex_key)
    if is_running:
        printdbg("An instance of Sentinel is already running -- aborting.")
        sys.exit(1)
    else:
        Transient.set(mutex_key, misc.now(), timeout_seconds)

    # locked to this instance -- perform main logic here
    main()

    Transient.delete(mutex_key)
