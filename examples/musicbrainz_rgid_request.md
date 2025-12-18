curl -sS -G 'https://musicbrainz.org/ws/2/recording' \                                                                                              ─╯
          -H "User-Agent: $UA" \
          --data-urlencode 'fmt=json' \
          --data-urlencode 'limit=25' \
          --data-urlencode 'query=recording:"Smells Like Teen Spirit" AND rgid:"1b022e01-4da6-387b-8658-8678046e4cef"'