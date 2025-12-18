curl -sS -G 'https://musicbrainz.org/ws/2/recording' \                                                                                              ─╯
          -H "User-Agent: $UA" \
          --data-urlencode 'fmt=json' \
          --data-urlencode 'limit=25' \
          --data-urlencode 'query=recording:"Smells Like Teen Spirit" AND artist:"Nirvana" AND status:"official" AND primarytype:"album" AND -secondarytype:live AND -secondarytype:compilation AND -secondarytype:remix'