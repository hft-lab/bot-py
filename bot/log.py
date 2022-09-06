import logging

FORMAT = '%(asctime)s %(levelname)s %(filename)s:%(lineno)d %(message)s (%(funcName)s)'
logging.basicConfig(format=FORMAT)

log = logging.getLogger('bot-py')
log.setLevel(logging.DEBUG)
log.info("logger configured")
