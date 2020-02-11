import os
class BaseConfig(object):
    DEBUG = False
    #uran24
    SECRET_KEY = '\x11L\xd8v\x96\x04\xa7<\xb5\xc9\xb1v\xc5\x13\x96\xcb\x8f\xd1\xe5n\x82E\x81\xe6'
    UPLOAD_FOLDER = '/tmp/'
    ALLOWED_EXTENSIONS = set(['txt','pdf','jpeg','png','bmp'])

class DevelopmentConfig(BaseConfig):
    DEBUG = True

class StagingConfig(BaseConfig):
    DEBUG = False

class ProductionConfig(BaseConfig):
    DEBUG = False