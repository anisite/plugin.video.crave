# ===================================================================
#
#   LOGIN HANDLER CONFIG
#
# ===================================================================

CLIENT_ID = "crave-web"
CLIENT_PASS = 'default'





# ===================================================================
#
#   GRAPHQL CONFIG
#
# ===================================================================

RTE_APP_ID = 'contentid/app-crave'





# ===================================================================
#
#   SUBSCRIPTIONS CONFIG
#
# ===================================================================

DESTINATION_TO_SUBSCRIPTION = {
  'starz_atexace':      'starz',
  'crave_atexace':      'crave',
  'crave_atexace_avod': 'crave',
  'se_atexace':         'superecran'
}

SUBSCRIPTION_NAME_TO_PACKAGE_NAME = {
  'STARZ':       'starz_atexace',
  'CRAVE':       'crave_atexace',
  'CRAVE_AVOD':  'crave_atexace_avod',
  'SUPER_ECRAN': 'se_atexace'
}


SCOPE_TO_SUBSCRIPTION_NAME = {
  'crave_total': 'CRAVE_TOTAL',
  'cravep':      'CRAVE_PLUS',
  'cravetv':     'CRAVE',
  'se':          'SUPER_ECRAN',
  'starz':       'STARZ'
}

# Maps GraphQL resourceCodes to CAPI package names for access checking
RESOURCE_CODE_TO_PACKAGE_NAME = {
  'cravetv':   'crave_atexace',
  'craveads':  'crave_atexace_avod',
  'se':        'se_atexace',
  'starz':     'starz_atexace',
}





# ===================================================================
#
#   HEADERS
#
# ===================================================================

BASE_HEADERS = {
  'accept-encoding': 'gzip',
  'connection': 'Keep-Alive',
  'user-agent': 'okhttp/4.9.0'
}

CAPI_HEADERS = {
  'accept-encoding': 'identity',
  'connection': 'Keep-Alive',
  'user-agent': 'okhttp/4.9.0'
}

HEADERS = {
  'accept': 'application/json',
  'accept-encoding': 'gzip',
  'connection': 'Keep-Alive',
  'content-type': 'application/json; charset=utf-8',
  'graphql-client-platform': 'entpay_android',
  'user-agent': 'okhttp/4.9.0'
}