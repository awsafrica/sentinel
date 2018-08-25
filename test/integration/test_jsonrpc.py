import pytest
import sys
import os
import re
os.environ['SENTINEL_ENV'] = 'test'
os.environ['SENTINEL_CONFIG'] = os.path.normpath(os.path.join(os.path.dirname(__file__), '../test_sentinel.conf'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import config

from brixcoind import BrixcoinDaemon
from brixcoin_config import BrixcoinConfig


def test_brixcoind():
    config_text = BrixcoinConfig.slurp_config_file(config.brixcoin_conf)
    network = 'mainnet'
    is_testnet = False
    genesis_hash = u'0000088ffb1796ef87cc546f5f3d7d841e58eaefdd03448cc16e73c8f8bd4add'
    for line in config_text.split("\n"):
        if line.startswith('testnet=1'):
            network = 'testnet'
            is_testnet = True
            genesis_hash = u'0000088ffb1796ef87cc546f5f3d7d841e58eaefdd03448cc16e73c8f8bd4add'

    creds = BrixcoinConfig.get_rpc_creds(config_text, network)
    brixcoind = BrixcoinDaemon(**creds)
    assert brixcoind.rpc_command is not None

    assert hasattr(brixcoind, 'rpc_connection')

    # Brixcoin testnet block 0 hash == 0000088ffb1796ef87cc546f5f3d7d841e58eaefdd03448cc16e73c8f8bd4add
    # test commands without arguments
    info = brixcoind.rpc_command('getinfo')
    info_keys = [
        'blocks',
        'connections',
        'difficulty',
        'errors',
        'protocolversion',
        'proxy',
        'testnet',
        'timeoffset',
        'version',
    ]
    for key in info_keys:
        assert key in info
    assert info['testnet'] is is_testnet

    # test commands with args
    assert brixcoind.rpc_command('getblockhash', 0) == genesis_hash
