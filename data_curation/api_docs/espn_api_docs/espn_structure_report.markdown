# ESPN Endpoint Samples

Generated from the ESPN basketball docs in `docs/`.

## getCalendars

- Doc: `docs/sports/basketball.md`
- Section: `Seasons & Calendar`
- API family: `core-v2`
- URL pattern: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/{league}/calendar`
- Sample URL: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/calendar`
- Query params: `dates, page, limit, dates, groups, smartdates, advance, utcOffset, weeks, seasontype`

```python
import requests

url = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/calendar'
params = {
    'dates': '20250320',
    'page': 1,
    'limit': 25,
    'utcOffset': -7,
    'seasontype': 2,
}
response = requests.get(url, params=params, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## getSeasons

- Doc: `docs/sports/basketball.md`
- Section: `Seasons & Calendar`
- API family: `core-v2`
- URL pattern: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/{league}/seasons`
- Sample URL: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/seasons`
- Query params: `page, limit, utcOffset, dates, start, end, eventsback, eventsforward, eventsrange, eventcompleted, groups, profile, competitions.types, types, season, weeks, tournamentId, dates, sort, type, date, group, position, week, qualified, types, limit, page, sort, position, status, sort, sortByRanks, stats, groupId, position, qualified, rookie, international, category, type, sort, sortByRanks, stats, groupId, qualified, category, sort, groupId, allStar, group, gender, types, country, association, lastNameInitial, lastName, active, statuses, sort, position, dates, groups, smartdates, advance, utcOffset, weeks, seasontype`

```python
import requests

url = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/seasons'
params = {
    'page': 1,
    'limit': 25,
    'utcOffset': -7,
    'dates': '20250320',
    'types': 2,
    'season': 2025,
    'sort': 'asc',
    'type': 2,
    'date': '2025-03-15',
    'group': 7,
    'week': 1,
    'qualified': 'true',
    'active': 'true',
    'seasontype': 2,
}
response = requests.get(url, params=params, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## getAthletes

- Doc: `docs/sports/basketball.md`
- Section: `Seasons & Calendar`
- API family: `core-v2`
- URL pattern: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/{league}/seasons/{season}/athletes`
- Sample URL: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/seasons/2025/athletes`
- Query params: `active, sort, page, limit, seasontypes, played, teamtypes, group, gender, types, country, association, lastNameInitial, lastName, active, statuses, sort, position`

```python
import requests

url = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/seasons/2025/athletes'
params = {
    'active': 'true',
    'sort': 'asc',
    'page': 1,
    'limit': 25,
    'group': 7,
    'types': 2,
}
response = requests.get(url, params=params, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## getDraftByYear

- Doc: `docs/sports/basketball.md`
- Section: `Seasons & Calendar`
- API family: `core-v2`
- URL pattern: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/{league}/seasons/{season}/draft`
- Sample URL: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/seasons/2025/draft`
- Query params: `page, limit, available, position, team, sort, filter`

```python
import requests

url = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/seasons/2025/draft'
params = {
    'page': 1,
    'limit': 25,
    'team': 13,
    'sort': 'asc',
}
response = requests.get(url, params=params, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## getFreeAgents

- Doc: `docs/sports/basketball.md`
- Section: `Seasons & Calendar`
- API family: `core-v2`
- URL pattern: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/{league}/seasons/{season}/freeagents`
- Sample URL: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/seasons/2025/freeagents`
- Query params: `page, limit, types, oldteams, newteams, position, sort`

```python
import requests

url = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/seasons/2025/freeagents'
params = {
    'page': 1,
    'limit': 25,
    'types': 2,
    'sort': 'asc',
}
response = requests.get(url, params=params, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## getManufacturers

- Doc: `docs/sports/basketball.md`
- Section: `Seasons & Calendar`
- API family: `core-v2`
- URL pattern: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/{league}/seasons/{season}/manufacturers`
- Sample URL: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/seasons/2025/manufacturers`
- Query params: `page, limit`

```python
import requests

url = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/seasons/2025/manufacturers'
params = {
    'page': 1,
    'limit': 25,
}
response = requests.get(url, params=params, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## getTeams

- Doc: `docs/sports/basketball.md`
- Section: `Teams`
- API family: `core-v2`
- URL pattern: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/{league}/teams`
- Sample URL: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/teams`
- Query params: `page, limit, utcOffset, dates, start, end, eventsback, eventsforward, eventsrange, eventcompleted, groups, profile, competitions.types, types, season, weeks, tournamentId, active, national, start, group, dates, recent, types, winnertype, date, eventsback, excludestatuses, includestatuses, dates, groups, smartdates, advance, utcOffset, weeks, seasontype`
- Related schema: `Teams`
- Documented top-level keys: `sports, count, pageIndex, pageSize`

```python
import requests

url = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/teams'
params = {
    'page': 1,
    'limit': 25,
    'utcOffset': -7,
    'dates': '20250320',
    'types': 2,
    'season': 2025,
    'active': 'true',
    'group': 7,
    'date': '2025-03-15',
    'seasontype': 2,
}
response = requests.get(url, params=params, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## getAthletes

- Doc: `docs/sports/basketball.md`
- Section: `Athletes / Players`
- API family: `core-v2`
- URL pattern: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/{league}/athletes`
- Sample URL: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/athletes`
- Query params: `page, limit, group, gender, types, country, association, lastNameInitial, lastName, active, statuses, sort, position`

```python
import requests

url = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/athletes'
params = {
    'page': 1,
    'limit': 25,
    'group': 7,
    'types': 2,
    'active': 'true',
    'sort': 'asc',
}
response = requests.get(url, params=params, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## getEvent

- Doc: `docs/sports/basketball.md`
- Section: `Events / Games`
- API family: `core-v2`
- URL pattern: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/{league}/events/{event}`
- Sample URL: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/401765432`
- Query params: `page, limit`

```python
import requests

url = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/401765432'
params = {
    'page': 1,
    'limit': 25,
}
response = requests.get(url, params=params, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## getCompetition

- Doc: `docs/sports/basketball.md`
- Section: `Events / Games`
- API family: `core-v2`
- URL pattern: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/{league}/events/{event}/competitions/{competition}`
- Sample URL: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/401765432/competitions/401765432`
- Query params: `page, limit, date, group, position, week, qualified, types, limit, page, types, period, sort, source, showsubplays`

```python
import requests

url = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/401765432/competitions/401765432'
params = {
    'page': 1,
    'limit': 25,
    'date': '2025-03-15',
    'group': 7,
    'week': 1,
    'qualified': 'true',
    'types': 2,
    'period': 1,
    'sort': 'asc',
}
response = requests.get(url, params=params, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## getBroadcasts

- Doc: `docs/sports/basketball.md`
- Section: `Events / Games`
- API family: `core-v2`
- URL pattern: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/{league}/events/{event}/competitions/{competition}/broadcasts`
- Sample URL: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/401765432/competitions/401765432/broadcasts`
- Query params: `lang, region, page, limit`

```python
import requests

url = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/401765432/competitions/401765432/broadcasts'
params = {
    'lang': 'en',
    'region': 'us',
    'page': 1,
    'limit': 25,
}
response = requests.get(url, params=params, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## getCompetitor

- Doc: `docs/sports/basketball.md`
- Section: `Events / Games`
- API family: `core-v2`
- URL pattern: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/{league}/events/{event}/competitions/{competition}/competitors/{competitor}`
- Sample URL: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/401765432/competitions/401765432/competitors/13`
- Query params: `page, limit, date, group, position, week, qualified, types, limit, page`

```python
import requests

url = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/401765432/competitions/401765432/competitors/13'
params = {
    'page': 1,
    'limit': 25,
    'date': '2025-03-15',
    'group': 7,
    'week': 1,
    'qualified': 'true',
    'types': 2,
}
response = requests.get(url, params=params, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## getCompetitionOdds

- Doc: `docs/sports/basketball.md`
- Section: `Events / Games`
- API family: `core-v2`
- URL pattern: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/{league}/events/{event}/competitions/{competition}/odds`
- Sample URL: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/401765432/competitions/401765432/odds`
- Query params: `provider.priority, page, limit`
- Related schema: `Betting Odds`

```python
import requests

url = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/401765432/competitions/401765432/odds'
params = {
    'provider.priority': 1,
    'page': 1,
    'limit': 25,
}
response = requests.get(url, params=params, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## getOfficials

- Doc: `docs/sports/basketball.md`
- Section: `Events / Games`
- API family: `core-v2`
- URL pattern: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/{league}/events/{event}/competitions/{competition}/officials`
- Sample URL: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/401765432/competitions/401765432/officials`
- Query params: `page, limit`

```python
import requests

url = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/401765432/competitions/401765432/officials'
params = {
    'page': 1,
    'limit': 25,
}
response = requests.get(url, params=params, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## getPersonnel

- Doc: `docs/sports/basketball.md`
- Section: `Events / Games`
- API family: `core-v2`
- URL pattern: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/{league}/events/{event}/competitions/{competition}/plays/{play}/personnel`
- Sample URL: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/401765432/competitions/401765432/plays/4017654340001/personnel`
- Query params: `page, limit`

```python
import requests

url = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/401765432/competitions/401765432/plays/4017654340001/personnel'
params = {
    'page': 1,
    'limit': 25,
}
response = requests.get(url, params=params, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## getMedia

- Doc: `docs/sports/basketball.md`
- Section: `News & Media`
- API family: `core-v2`
- URL pattern: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/{league}/media`
- Sample URL: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/media`
- Query params: `page, limit`

```python
import requests

url = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/media'
params = {
    'page': 1,
    'limit': 25,
}
response = requests.get(url, params=params, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## getRankings

- Doc: `docs/sports/basketball.md`
- Section: `Rankings & Awards`
- API family: `core-v2`
- URL pattern: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/{league}/rankings`
- Sample URL: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/rankings`
- Query params: `page, limit`

```python
import requests

url = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/rankings'
params = {
    'page': 1,
    'limit': 25,
}
response = requests.get(url, params=params, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## getVenues

- Doc: `docs/sports/basketball.md`
- Section: `Venues`
- API family: `core-v2`
- URL pattern: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/{league}/venues`
- Sample URL: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/venues`
- Query params: `page, limit`

```python
import requests

url = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/venues'
params = {
    'page': 1,
    'limit': 25,
}
response = requests.get(url, params=params, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## getCasinos

- Doc: `docs/sports/basketball.md`
- Section: `Other`
- API family: `core-v2`
- URL pattern: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/{league}/casinos`
- Sample URL: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/casinos`
- Query params: `page, limit`

```python
import requests

url = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/casinos'
params = {
    'page': 1,
    'limit': 25,
}
response = requests.get(url, params=params, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## getCircuits

- Doc: `docs/sports/basketball.md`
- Section: `Other`
- API family: `core-v2`
- URL pattern: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/{league}/circuits`
- Sample URL: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/circuits`
- Query params: `page, limit`

```python
import requests

url = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/circuits'
params = {
    'page': 1,
    'limit': 25,
}
response = requests.get(url, params=params, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## getCountries

- Doc: `docs/sports/basketball.md`
- Section: `Other`
- API family: `core-v2`
- URL pattern: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/{league}/countries`
- Sample URL: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/countries`
- Query params: `page, limit`

```python
import requests

url = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/countries'
params = {
    'page': 1,
    'limit': 25,
}
response = requests.get(url, params=params, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## getFranchises

- Doc: `docs/sports/basketball.md`
- Section: `Other`
- API family: `core-v2`
- URL pattern: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/{league}/franchises`
- Sample URL: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/franchises`
- Query params: `page, limit`

```python
import requests

url = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/franchises'
params = {
    'page': 1,
    'limit': 25,
}
response = requests.get(url, params=params, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## getPositions

- Doc: `docs/sports/basketball.md`
- Section: `Other`
- API family: `core-v2`
- URL pattern: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/{league}/positions`
- Sample URL: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/positions`
- Query params: `page, limit`

```python
import requests

url = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/positions'
params = {
    'page': 1,
    'limit': 25,
}
response = requests.get(url, params=params, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## getProviders

- Doc: `docs/sports/basketball.md`
- Section: `Other`
- API family: `core-v2`
- URL pattern: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/{league}/providers`
- Sample URL: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/providers`
- Query params: `page, limit`

```python
import requests

url = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/providers'
params = {
    'page': 1,
    'limit': 25,
}
response = requests.get(url, params=params, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## getRecruitingSeasons

- Doc: `docs/sports/basketball.md`
- Section: `Other`
- API family: `core-v2`
- URL pattern: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/{league}/recruiting`
- Sample URL: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/recruiting`
- Query params: `page, limit, sort, position, status`

```python
import requests

url = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/recruiting'
params = {
    'page': 1,
    'limit': 25,
    'sort': 'asc',
}
response = requests.get(url, params=params, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## getCurrentSeason

- Doc: `docs/sports/basketball.md`
- Section: `Other`
- API family: `core-v2`
- URL pattern: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/{league}/season`
- Sample URL: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/season`
- Query params: `page, limit`

```python
import requests

url = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/season'
params = {
    'page': 1,
    'limit': 25,
}
response = requests.get(url, params=params, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## getTournaments

- Doc: `docs/sports/basketball.md`
- Section: `Other`
- API family: `core-v2`
- URL pattern: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/{league}/tournaments`
- Sample URL: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/tournaments`
- Query params: `majorsOnly, page, limit`

```python
import requests

url = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/tournaments'
params = {
    'page': 1,
    'limit': 25,
}
response = requests.get(url, params=params, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## getAthletes

- Doc: `docs/sports/basketball.md`
- Section: `V3 Endpoints`
- API family: `core-v3`
- URL pattern: `https://sports.core.api.espn.com/v3/sports/{sport}/athletes`
- Sample URL: `https://sports.core.api.espn.com/v3/sports/basketball/athletes`
- Query params: `page, limit, _hoist, _help, _trace, _nocache, enable, disable, pq, q, page, limit, lang, region, utcOffset, dates, weeks, advance, event.recurring, ids, type, types, seasontypes, calendar.type, calendar.groups, status, statuses, groups, provider, provider.priority, site, league.type, split, splits, record.splits, record.seasontype, statistic.splits, statistic.seasontype, statistic.qualified, statistic.context, sort, roster.positions, roster.athletes, team.athletes, powerindex.rundatetimekey, eventsback, eventsforward, eventsrange, eventstates, eventresults, seek, tournaments, competitions, competition.types, teams, situation.play, oldteams, newteams, played, period, position, filter, available, active, ids.sportware, profile, opponent, eventId, homeAway, season, athlete.position, postalCode, award.type, notes.type, tidbit.type, networks, bets.promotion, guids, competitors, source`

```python
import requests

url = 'https://sports.core.api.espn.com/v3/sports/basketball/athletes'
params = {
    'page': 1,
    'limit': 25,
    'lang': 'en',
    'region': 'us',
    'utcOffset': -7,
    'dates': '20250320',
    'type': 2,
    'types': 2,
    'provider.priority': 1,
    'sort': 'asc',
    'period': 1,
    'active': 'true',
    'eventId': '401765432',
    'season': 2025,
}
response = requests.get(url, params=params, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## getLeague

- Doc: `docs/sports/basketball.md`
- Section: `V3 Endpoints`
- API family: `core-v3`
- URL pattern: `https://sports.core.api.espn.com/v3/sports/{sport}/{league}`
- Sample URL: `https://sports.core.api.espn.com/v3/sports/basketball/nba`
- Query params: `page, limit, _hoist, _help, _trace, _nocache, enable, disable, pq, q, page, limit, lang, region, utcOffset, dates, weeks, advance, event.recurring, ids, type, types, seasontypes, calendar.type, calendar.groups, status, statuses, groups, provider, provider.priority, site, league.type, split, splits, record.splits, record.seasontype, statistic.splits, statistic.seasontype, statistic.qualified, statistic.context, sort, roster.positions, roster.athletes, team.athletes, powerindex.rundatetimekey, eventsback, eventsforward, eventsrange, eventstates, eventresults, seek, tournaments, competitions, competition.types, teams, situation.play, oldteams, newteams, played, period, position, filter, available, active, ids.sportware, profile, opponent, eventId, homeAway, season, athlete.position, postalCode, award.type, notes.type, tidbit.type, networks, bets.promotion, guids, competitors, source`

```python
import requests

url = 'https://sports.core.api.espn.com/v3/sports/basketball/nba'
params = {
    'page': 1,
    'limit': 25,
    'lang': 'en',
    'region': 'us',
    'utcOffset': -7,
    'dates': '20250320',
    'type': 2,
    'types': 2,
    'provider.priority': 1,
    'sort': 'asc',
    'period': 1,
    'active': 'true',
    'eventId': '401765432',
    'season': 2025,
}
response = requests.get(url, params=params, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## getSeason

- Doc: `docs/sports/basketball.md`
- Section: `V3 Endpoints`
- API family: `core-v3`
- URL pattern: `https://sports.core.api.espn.com/v3/sports/{sport}/{league}/seasons/{season}`
- Sample URL: `https://sports.core.api.espn.com/v3/sports/basketball/nba/seasons/2025`
- Query params: `page, limit, _hoist, _help, _trace, _nocache, enable, disable, pq, q, page, limit, lang, region, utcOffset, dates, weeks, advance, event.recurring, ids, type, types, seasontypes, calendar.type, calendar.groups, status, statuses, groups, provider, provider.priority, site, league.type, split, splits, record.splits, record.seasontype, statistic.splits, statistic.seasontype, statistic.qualified, statistic.context, sort, roster.positions, roster.athletes, team.athletes, powerindex.rundatetimekey, eventsback, eventsforward, eventsrange, eventstates, eventresults, seek, tournaments, competitions, competition.types, teams, situation.play, oldteams, newteams, played, period, position, filter, available, active, ids.sportware, profile, opponent, eventId, homeAway, season, athlete.position, postalCode, award.type, notes.type, tidbit.type, networks, bets.promotion, guids, competitors, source`

```python
import requests

url = 'https://sports.core.api.espn.com/v3/sports/basketball/nba/seasons/2025'
params = {
    'page': 1,
    'limit': 25,
    'lang': 'en',
    'region': 'us',
    'utcOffset': -7,
    'dates': '20250320',
    'type': 2,
    'types': 2,
    'provider.priority': 1,
    'sort': 'asc',
    'period': 1,
    'active': 'true',
    'eventId': '401765432',
    'season': 2025,
}
response = requests.get(url, params=params, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## site:Resource

- Doc: `docs/sports/basketball.md`
- Section: `Site API Endpoints`
- API family: `site-v2`
- URL pattern: `https://site.api.espn.com/apis/site/v2/sports/basketball/{league}/Resource`
- Sample URL: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/Resource`
- Note: Description

```python
import requests

url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/Resource'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## site:scoreboard

- Doc: `docs/sports/basketball.md`
- Section: `Site API Endpoints`
- API family: `site-v2`
- URL pattern: `https://site.api.espn.com/apis/site/v2/sports/basketball/{league}/scoreboard`
- Sample URL: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard`
- Note: Live scores & schedules
- Related schema: `Scoreboard`
- Documented top-level keys: `leagues, events`

```python
import requests

url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## site:scoreboard?dates={YYYYMMDD}

- Doc: `docs/sports/basketball.md`
- Section: `Site API Endpoints`
- API family: `site-v2`
- URL pattern: `https://site.api.espn.com/apis/site/v2/sports/basketball/{league}/scoreboard?dates={YYYYMMDD}`
- Sample URL: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={YYYYMMDD}`
- Note: Scores for a specific date
- Related schema: `Scoreboard`
- Documented top-level keys: `leagues, events`

```python
import requests

url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={YYYYMMDD}'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## site:teams

- Doc: `docs/sports/basketball.md`
- Section: `Site API Endpoints`
- API family: `site-v2`
- URL pattern: `https://site.api.espn.com/apis/site/v2/sports/basketball/{league}/teams`
- Sample URL: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams`
- Note: All teams
- Related schema: `Teams`
- Documented top-level keys: `sports, count, pageIndex, pageSize`

```python
import requests

url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## site:teams/{id}

- Doc: `docs/sports/basketball.md`
- Section: `Site API Endpoints`
- API family: `site-v2`
- URL pattern: `https://site.api.espn.com/apis/site/v2/sports/basketball/{league}/teams/{id}`
- Sample URL: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/13`
- Note: Single team
- Related schema: `Teams`
- Documented top-level keys: `sports, count, pageIndex, pageSize`

```python
import requests

url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/13'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## site:teams/{id}/roster

- Doc: `docs/sports/basketball.md`
- Section: `Site API Endpoints`
- API family: `site-v2`
- URL pattern: `https://site.api.espn.com/apis/site/v2/sports/basketball/{league}/teams/{id}/roster`
- Sample URL: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/13/roster`
- Note: Team roster
- Related schema: `Team Roster`
- Documented top-level keys: `team, athletes, coach`

```python
import requests

url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/13/roster'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## site:teams/{id}/schedule

- Doc: `docs/sports/basketball.md`
- Section: `Site API Endpoints`
- API family: `site-v2`
- URL pattern: `https://site.api.espn.com/apis/site/v2/sports/basketball/{league}/teams/{id}/schedule`
- Sample URL: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/13/schedule`
- Note: Team schedule
- Related schema: `Teams`
- Documented top-level keys: `sports, count, pageIndex, pageSize`

```python
import requests

url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/13/schedule'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## site:teams/{id}/record

- Doc: `docs/sports/basketball.md`
- Section: `Site API Endpoints`
- API family: `site-v2`
- URL pattern: `https://site.api.espn.com/apis/site/v2/sports/basketball/{league}/teams/{id}/record`
- Sample URL: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/13/record`
- Note: Team record
- Related schema: `Teams`
- Documented top-level keys: `sports, count, pageIndex, pageSize`

```python
import requests

url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/13/record'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## site:teams/{id}/news

- Doc: `docs/sports/basketball.md`
- Section: `Site API Endpoints`
- API family: `site-v2`
- URL pattern: `https://site.api.espn.com/apis/site/v2/sports/basketball/{league}/teams/{id}/news`
- Sample URL: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/13/news`
- Note: Team news
- Related schema: `Teams`
- Documented top-level keys: `sports, count, pageIndex, pageSize`

```python
import requests

url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/13/news'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## site:teams/{id}/injuries

- Doc: `docs/sports/basketball.md`
- Section: `Site API Endpoints`
- API family: `site-v2`
- URL pattern: `https://site.api.espn.com/apis/site/v2/sports/basketball/{league}/teams/{id}/injuries`
- Sample URL: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/13/injuries`
- Note: Team injury report
- Related schema: `Team Injuries`
- Documented top-level keys: `team, injuries`

```python
import requests

url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/13/injuries'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## site:teams/{id}/leaders

- Doc: `docs/sports/basketball.md`
- Section: `Site API Endpoints`
- API family: `site-v2`
- URL pattern: `https://site.api.espn.com/apis/site/v2/sports/basketball/{league}/teams/{id}/leaders`
- Sample URL: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/13/leaders`
- Note: Team statistical leaders
- Related schema: `Teams`
- Documented top-level keys: `sports, count, pageIndex, pageSize`

```python
import requests

url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/13/leaders'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## site:teams/{id}/depth-charts

- Doc: `docs/sports/basketball.md`
- Section: `Site API Endpoints`
- API family: `site-v2`
- URL pattern: `https://site.api.espn.com/apis/site/v2/sports/basketball/{league}/teams/{id}/depth-charts`
- Sample URL: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/13/depth-charts`
- Note: Depth charts
- Related schema: `Teams`
- Documented top-level keys: `sports, count, pageIndex, pageSize`

```python
import requests

url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/13/depth-charts'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## site:injuries

- Doc: `docs/sports/basketball.md`
- Section: `Site API Endpoints`
- API family: `site-v2`
- URL pattern: `https://site.api.espn.com/apis/site/v2/sports/basketball/{league}/injuries`
- Sample URL: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries`
- Note: **League-wide** injury report (all teams)
- Related schema: `League-wide Injuries`
- Documented top-level keys: `timestamp, status, season, injuries`

```python
import requests

url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## site:transactions

- Doc: `docs/sports/basketball.md`
- Section: `Site API Endpoints`
- API family: `site-v2`
- URL pattern: `https://site.api.espn.com/apis/site/v2/sports/basketball/{league}/transactions`
- Sample URL: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/transactions`
- Note: Recent signings, trades, waivers

```python
import requests

url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/transactions'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## site:statistics

- Doc: `docs/sports/basketball.md`
- Section: `Site API Endpoints`
- API family: `site-v2`
- URL pattern: `https://site.api.espn.com/apis/site/v2/sports/basketball/{league}/statistics`
- Sample URL: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/statistics`
- Note: League statistical leaders

```python
import requests

url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/statistics'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## site:groups

- Doc: `docs/sports/basketball.md`
- Section: `Site API Endpoints`
- API family: `site-v2`
- URL pattern: `https://site.api.espn.com/apis/site/v2/sports/basketball/{league}/groups`
- Sample URL: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/groups`
- Note: Conferences and divisions

```python
import requests

url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/groups'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## site:draft

- Doc: `docs/sports/basketball.md`
- Section: `Site API Endpoints`
- API family: `site-v2`
- URL pattern: `https://site.api.espn.com/apis/site/v2/sports/basketball/{league}/draft`
- Sample URL: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/draft`
- Note: Draft board (NBA only)

```python
import requests

url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/draft'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## site:standings

- Doc: `docs/sports/basketball.md`
- Section: `Site API Endpoints`
- API family: `site-v2`
- URL pattern: `https://site.api.espn.com/apis/v2/sports/basketball/{league}/standings`
- Sample URL: `https://site.api.espn.com/apis/v2/sports/basketball/nba/standings`
- Note: ⚠️ Stub only — see note below
- Related schema: `Standings`
- Documented top-level keys: `uid, season, fullViewLink, children`

```python
import requests

url = 'https://site.api.espn.com/apis/v2/sports/basketball/nba/standings'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## site:news

- Doc: `docs/sports/basketball.md`
- Section: `Site API Endpoints`
- API family: `site-v2`
- URL pattern: `https://site.api.espn.com/apis/site/v2/sports/basketball/{league}/news`
- Sample URL: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/news`
- Note: Latest news

```python
import requests

url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/news'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## site:athletes/{id}/news

- Doc: `docs/sports/basketball.md`
- Section: `Site API Endpoints`
- API family: `site-v2`
- URL pattern: `https://site.api.espn.com/apis/site/v2/sports/basketball/{league}/athletes/{id}/news`
- Sample URL: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/athletes/3136776/news`
- Note: Athlete-specific news

```python
import requests

url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/athletes/3136776/news'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## site:summary?event={id}

- Doc: `docs/sports/basketball.md`
- Section: `Site API Endpoints`
- API family: `site-v2`
- URL pattern: `https://site.api.espn.com/apis/site/v2/sports/basketball/{league}/summary?event={id}`
- Sample URL: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=401765432`
- Note: Full game summary + boxscore
- Related schema: `Game Summary`
- Documented top-level keys: `boxscore, plays, leaders, broadcasts, predictor`

```python
import requests

url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=401765432'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## site:rankings

- Doc: `docs/sports/basketball.md`
- Section: `Site API Endpoints`
- API family: `site-v2`
- URL pattern: `https://site.api.espn.com/apis/site/v2/sports/basketball/{league}/rankings`
- Sample URL: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/rankings`
- Note: Poll rankings (NCAA leagues only)

```python
import requests

url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/rankings'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## Full game package

- Doc: `docs/sports/basketball.md`
- Section: `CDN Game Data`
- API family: `cdn`
- URL pattern: `https://cdn.espn.com/core/nba/game?xhr=1&gameId={EVENT_ID}`
- Sample URL: `https://cdn.espn.com/core/nba/game?xhr=1&gameId=401765432`

```python
import requests

url = 'https://cdn.espn.com/core/nba/game?xhr=1&gameId=401765432'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## Specific views

- Doc: `docs/sports/basketball.md`
- Section: `CDN Game Data`
- API family: `cdn`
- URL pattern: `https://cdn.espn.com/core/nba/boxscore?xhr=1&gameId={EVENT_ID}`
- Sample URL: `https://cdn.espn.com/core/nba/boxscore?xhr=1&gameId=401765432`

```python
import requests

url = 'https://cdn.espn.com/core/nba/boxscore?xhr=1&gameId=401765432'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## playbyplay?xhr=1&gameId={EVENT_ID}

- Doc: `docs/sports/basketball.md`
- Section: `CDN Game Data`
- API family: `cdn`
- URL pattern: `https://cdn.espn.com/core/nba/playbyplay?xhr=1&gameId={EVENT_ID}`
- Sample URL: `https://cdn.espn.com/core/nba/playbyplay?xhr=1&gameId=401765432`

```python
import requests

url = 'https://cdn.espn.com/core/nba/playbyplay?xhr=1&gameId=401765432'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## matchup?xhr=1&gameId={EVENT_ID}

- Doc: `docs/sports/basketball.md`
- Section: `CDN Game Data`
- API family: `cdn`
- URL pattern: `https://cdn.espn.com/core/nba/matchup?xhr=1&gameId={EVENT_ID}`
- Sample URL: `https://cdn.espn.com/core/nba/matchup?xhr=1&gameId=401765432`

```python
import requests

url = 'https://cdn.espn.com/core/nba/matchup?xhr=1&gameId=401765432'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## scoreboard?xhr=1

- Doc: `docs/sports/basketball.md`
- Section: `CDN Game Data`
- API family: `cdn`
- URL pattern: `https://cdn.espn.com/core/nba/scoreboard?xhr=1`
- Sample URL: `https://cdn.espn.com/core/nba/scoreboard?xhr=1`
- Related schema: `Scoreboard`
- Documented top-level keys: `leagues, events`

```python
import requests

url = 'https://cdn.espn.com/core/nba/scoreboard?xhr=1'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## Player overview (stats snapshot + next game + rotowire)

- Doc: `docs/sports/basketball.md`
- Section: `Athlete Data (common/v3)`
- API family: `common-v3`
- URL pattern: `https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{id}/overview`
- Sample URL: `https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/3136776/overview`
- Related schema: `Athlete Overview`
- Documented top-level keys: `statistics, news, nextGame, gameLog, rotowire`

```python
import requests

url = 'https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/3136776/overview'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## Season stats

- Doc: `docs/sports/basketball.md`
- Section: `Athlete Data (common/v3)`
- API family: `common-v3`
- URL pattern: `https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{id}/stats`
- Sample URL: `https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/3136776/stats`
- Related schema: `Athlete Stats`
- Documented top-level keys: `filters, teams, categories, glossary`

```python
import requests

url = 'https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/3136776/stats'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## Game log

- Doc: `docs/sports/basketball.md`
- Section: `Athlete Data (common/v3)`
- API family: `common-v3`
- URL pattern: `https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{id}/gamelog`
- Sample URL: `https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/3136776/gamelog`
- Related schema: `Athlete Gamelog`
- Documented top-level keys: `filters, labels, names, displayNames, events`

```python
import requests

url = 'https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/3136776/gamelog'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## Home/Away/Opponent splits

- Doc: `docs/sports/basketball.md`
- Section: `Athlete Data (common/v3)`
- API family: `common-v3`
- URL pattern: `https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{id}/splits`
- Sample URL: `https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/3136776/splits`
- Related schema: `Athlete Splits`
- Documented top-level keys: `filters, displayName, categories`

```python
import requests

url = 'https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/3136776/splits'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## Stats leaderboard (all athletes ranked)

- Doc: `docs/sports/basketball.md`
- Section: `Athlete Data (common/v3)`
- API family: `common-v3`
- URL pattern: `https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/statistics/byathlete`
- Sample URL: `https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/statistics/byathlete`
- Related schema: `Statistics by Athlete`
- Documented top-level keys: `pagination, league, currentSeason, athletes`

```python
import requests

url = 'https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/statistics/byathlete'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## Live bracket projections

- Doc: `docs/sports/basketball.md`
- Section: `Bracketology (NCAA Tournament)`
- API family: `specialized`
- URL pattern: `https://sports.core.api.espn.com/v2/tournament/{tournamentId}/seasons/{year}/bracketology`
- Sample URL: `https://sports.core.api.espn.com/v2/tournament/22/seasons/2025/bracketology`

```python
import requests

url = 'https://sports.core.api.espn.com/v2/tournament/22/seasons/2025/bracketology'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## Bracket snapshot at a specific iteration

- Doc: `docs/sports/basketball.md`
- Section: `Bracketology (NCAA Tournament)`
- API family: `specialized`
- URL pattern: `https://sports.core.api.espn.com/v2/tournament/{tournamentId}/seasons/{year}/bracketology/{iteration}`
- Sample URL: `https://sports.core.api.espn.com/v2/tournament/22/seasons/2025/bracketology/1`

```python
import requests

url = 'https://sports.core.api.espn.com/v2/tournament/22/seasons/2025/bracketology/1'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## Season BPI ratings

- Doc: `docs/sports/basketball.md`
- Section: `Power Index (BPI)`
- API family: `specialized`
- URL pattern: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/seasons/{year}/powerindex`
- Sample URL: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/seasons/2025/powerindex`

```python
import requests

url = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/seasons/2025/powerindex'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## BPI leaders

- Doc: `docs/sports/basketball.md`
- Section: `Power Index (BPI)`
- API family: `specialized`
- URL pattern: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/seasons/{year}/powerindex/leaders`
- Sample URL: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/seasons/2025/powerindex/leaders`

```python
import requests

url = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/seasons/2025/powerindex/leaders'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## BPI by team

- Doc: `docs/sports/basketball.md`
- Section: `Power Index (BPI)`
- API family: `specialized`
- URL pattern: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/seasons/{year}/powerindex/{teamId}`
- Sample URL: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/seasons/2025/powerindex/13`

```python
import requests

url = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/seasons/2025/powerindex/13'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## NBA scoreboard (today)

- Doc: `docs/sports/basketball.md`
- Section: `Example API Calls`
- API family: `example`
- URL pattern: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard`
- Sample URL: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard`
- Related schema: `Scoreboard`
- Documented top-level keys: `leagues, events`

```python
import requests

url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## NBA scoreboard for a specific date

- Doc: `docs/sports/basketball.md`
- Section: `Example API Calls`
- API family: `example`
- URL pattern: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=20250320`
- Sample URL: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=20250320`
- Related schema: `Scoreboard`
- Documented top-level keys: `leagues, events`

```python
import requests

url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=20250320'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## NBA standings (use /apis/v2/ — /apis/site/v2/ only returns a stub)

- Doc: `docs/sports/basketball.md`
- Section: `Example API Calls`
- API family: `example`
- URL pattern: `https://site.api.espn.com/apis/v2/sports/basketball/nba/standings`
- Sample URL: `https://site.api.espn.com/apis/v2/sports/basketball/nba/standings`
- Related schema: `Standings`
- Documented top-level keys: `uid, season, fullViewLink, children`

```python
import requests

url = 'https://site.api.espn.com/apis/v2/sports/basketball/nba/standings'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## LA Lakers roster

- Doc: `docs/sports/basketball.md`
- Section: `Example API Calls`
- API family: `example`
- URL pattern: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/13/roster`
- Sample URL: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/13/roster`
- Related schema: `Teams`
- Documented top-level keys: `sports, count, pageIndex, pageSize`

```python
import requests

url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/13/roster'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## LA Lakers injury report

- Doc: `docs/sports/basketball.md`
- Section: `Example API Calls`
- API family: `example`
- URL pattern: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/13/injuries`
- Sample URL: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/13/injuries`
- Related schema: `Teams`
- Documented top-level keys: `sports, count, pageIndex, pageSize`

```python
import requests

url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/13/injuries'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## Men's College Basketball scoreboard

- Doc: `docs/sports/basketball.md`
- Section: `Example API Calls`
- API family: `example`
- URL pattern: `https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard?dates=20250320-20250323`
- Sample URL: `https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard?dates=20250320-20250323`
- Related schema: `Scoreboard`
- Documented top-level keys: `leagues, events`

```python
import requests

url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard?dates=20250320-20250323'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## Get all basketball leagues (core API)

- Doc: `docs/sports/basketball.md`
- Section: `Example API Calls`
- API family: `example`
- URL pattern: `https://sports.core.api.espn.com/v2/sports/basketball/leagues`
- Sample URL: `https://sports.core.api.espn.com/v2/sports/basketball/leagues`

```python
import requests

url = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## NBA teams (core API)

- Doc: `docs/sports/basketball.md`
- Section: `Example API Calls`
- API family: `example`
- URL pattern: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/teams?limit=50`
- Sample URL: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/teams?limit=50`
- Related schema: `Teams`
- Documented top-level keys: `sports, count, pageIndex, pageSize`

```python
import requests

url = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/teams?limit=50'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## NBA athletes (core API)

- Doc: `docs/sports/basketball.md`
- Section: `Example API Calls`
- API family: `example`
- URL pattern: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/athletes?limit=100&active=true`
- Sample URL: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/athletes?limit=100&active=true`

```python
import requests

url = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/athletes?limit=100&active=true'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## NBA standings (core API)

- Doc: `docs/sports/basketball.md`
- Section: `Example API Calls`
- API family: `example`
- URL pattern: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/standings`
- Sample URL: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/standings`
- Related schema: `Standings`
- Documented top-level keys: `uid, season, fullViewLink, children`

```python
import requests

url = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/standings'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## WNBA teams

- Doc: `docs/sports/basketball.md`
- Section: `Example API Calls`
- API family: `example`
- URL pattern: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/wnba/teams`
- Sample URL: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/wnba/teams`
- Related schema: `Teams`
- Documented top-level keys: `sports, count, pageIndex, pageSize`

```python
import requests

url = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/wnba/teams'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```

## FIBA World Cup teams

- Doc: `docs/sports/basketball.md`
- Section: `Example API Calls`
- API family: `example`
- URL pattern: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/fiba/teams`
- Sample URL: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/fiba/teams`
- Related schema: `Teams`
- Documented top-level keys: `sports, count, pageIndex, pageSize`

```python
import requests

url = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/fiba/teams'
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
print(type(data).__name__)
if isinstance(data, dict):
    print(list(data.keys())[:20])
elif isinstance(data, list):
    print(f'items={len(data)}')
```
