# ===================================================================
#
#   HEADERS
#
# ===================================================================

HEADERS = {
  'accept': 'application/json',
  'accept-encoding': 'gzip',
  'connection': 'Keep-Alive',
  'content-type': 'application/json; charset=utf-8',
  'x-client-platform': 'platform_web',
  'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
  'origin': 'https://www.crave.ca',
  'referer': 'https://www.crave.ca/',
}




# ===================================================================
#
#   RTE API CONFIG
#
# ===================================================================

RTE_GRAPHQL_URL = 'https://rte-api.bellmedia.ca/graphql'
RTE_APP_ID = 'contentid/app-crave'

_SC = {'userMaturity': 'ADULT', 'userLanguage': 'FR'}  # placeholder, overridden at request time




# ===================================================================
#
#   RTE PAYLOADS
#
# ===================================================================

GET_APP_PAYLOAD = {
  'operationName': 'GetApp',
  'variables': {
    'id': RTE_APP_ID,
    'sessionContext': _SC,
    'isNonAdminUser': False
  },
  'query': (
    'query GetApp($sessionContext: SessionContext!, $id: String!) {'
    '  app(sessionContext: $sessionContext, id: $id) {'
    '    id title'
    '    navigation {'
    '      navigationLinks {'
    '        link {'
    '          displayTitle'
    '          action { ... on Screen { id path } __typename }'
    '          __typename'
    '        }'
    '      }'
    '    }'
    '  }'
    '}'
  )
}


GET_SCREEN_PAYLOAD = {
  'operationName': 'GetScreen',
  'variables': {
    'id': '',
    'sessionContext': _SC,
    'limit': 30
  },
  'query': (
    'query GetScreen($sessionContext: SessionContext!, $id: String!, $limit: Int, $cursor: String) {'
    '  screen(sessionContext: $sessionContext, id: $id) {'
    '    id title'
    '    navigation {'
    '      navigationLinks {'
    '        action { ... on Screen { id path } __typename }'
    '        displayTitle'
    '      }'
    '    }'
    '    screenContentsPage(limit: $limit, cursor: $cursor) {'
    '      cursor'
    '      screenContents {'
    '        __typename'
    '        ... on Container { id displayTitle style displayType }'
    '      }'
    '    }'
    '  }'
    '}'
  )
}


GET_CONTAINER_PAYLOAD = {
  'operationName': 'GetPosterRotator',
  'variables': {
    'id': '',
    'sessionContext': _SC,
    'limit': 50
  },
  'query': (
    'query GetPosterRotator($sessionContext: SessionContext!, $id: String!, $cursor: String, $limit: Int) {'
    '  container(sessionContext: $sessionContext, id: $id) {'
    '    id displayTitle'
    '    containerItemsPage(cursor: $cursor, limit: $limit) {'
    '      cursor'
    '      items {'
    '        ... on MediaMetadata {'
    '          __typename id path title mediaType locked'
    '          metadataImages { poster { url } }'
    '        }'
    '      }'
    '    }'
    '  }'
    '}'
  )
}


GET_SEARCH_PAYLOAD = {
  'operationName': 'GetSearch',
  'variables': {
    'sessionContext': _SC,
    'searchQuery': '',
    'pageNumber': 0,
    'pageSize': 50,
    'collection': 'ALL'
  },
  'query': (
    'query GetSearch($sessionContext: SessionContext!, $searchQuery: String!, $pageNumber: Int!, $pageSize: Int!, $collection: SearchCollectionType!) {'
    '  search('
    '    sessionContext: $sessionContext'
    '    searchRequest: {searchQuery: $searchQuery, pageNumber: $pageNumber, pageSize: $pageSize, collection: $collection}'
    '  ) {'
    '    pageSize hasMore found'
    '    mediaResults {'
    '      ... on MediaMetadata {'
    '        __typename id path title mediaType locked'
    '        metadataImages { poster { url } }'
    '      }'
    '    }'
    '  }'
    '}'
  )
}


GET_SHOWPAGE_PAYLOAD = {
  'operationName': 'GetShowpage',
  'variables': {
    'sessionContext': _SC,
    'ids': []
  },
  'query': (
    'query GetShowpage($sessionContext: SessionContext!, $ids: [String!]!) {'
    '  medias(sessionContext: $sessionContext, ids: $ids) {'
    '    id path title mediaType'
    '    description'
    '    productionYear'
    '    metadataImages { poster { url } thumbnail { url } }'
    '    seasons { id title seasonNumber }'
    '    firstContent {'
    '      id title contentType locked'
    '      duration { timeInSecs }'
    '      languageIndicators {'
    '        indicator indicatorLabel'
    '        languages { langCode displayTitle locked }'
    '      }'
    '    }'
    '  }'
    '}'
  )
}


GET_SEASON_PAYLOAD = {
  'operationName': 'GetContentBySeasonId',
  'variables': {
    'sessionContext': _SC,
    'id': '',
    'contentFormat': None
  },
  'query': (
    'query GetContentBySeasonId($sessionContext: SessionContext!, $id: String!, $contentFormat: ContentFormatRequest) {'
    '  contentsBySeasonId(sessionContext: $sessionContext, id: $id, contentFormat: $contentFormat) {'
    '    id path title episodeNumber locked'
    '    shortDescription'
    '    broadcastDate'
    '    duration { timeInSecs }'
    '    metadataImages { thumbnail { url } poster { url } }'
    '    languageIndicators {'
    '      indicator indicatorLabel'
    '      languages { langCode displayTitle locked }'
    '    }'
    '  }'
    '}'
  )
}
