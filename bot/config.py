import argparse
import configparser

args_parser = argparse.ArgumentParser(description='Run bot.')
args_parser.add_argument('--config', dest='conf', required=True, help='Config file in .ini format')
args = args_parser.parse_args()

config = configparser.ConfigParser()
config.read(args.conf)
