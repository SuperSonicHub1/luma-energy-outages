import pygit2
from datetime import datetime
from types import SimpleNamespace
import json
from csv import DictReader
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--savefig', action='store_true')
args = parser.parse_args()
interactive = not args.savefig

REGIONS = ['Arecibo', 'Bayamon', 'Carolina', 'Caguas', 'Mayaguez', 'Ponce', 'San Juan']
def normalize_name(name: str):
    return name.lower().replace(" ", "_")

# Processing

repo = pygit2.Repository('.')
last = repo[repo.head.target]
file = 'service_statistics.json'
commits = (commit for commit in repo.walk(last.id, pygit2.GIT_SORT_TIME | pygit2.GIT_SORT_REVERSE))
commits_blobs = (commit.tree / file for commit in commits if file in commit.tree)
blobs_contents = (blob.data for blob in commits_blobs)
service_statistics_objects = (json.loads(content) for content in blobs_contents)
outage_timeseries = sorted(
    (
        SimpleNamespace(
            timestamp=datetime.strptime(object['timestamp'], '%m/%d/%Y %I:%M %p'),
            total_clients_without_service=object['totals']['totalClientsWithoutService'],
            **{f'{normalize_name(region["name"])}_clients_without_service': region['totalClientsWithoutService'] for region in object['regions']},
            object=object,
        )
        for object
        in service_statistics_objects
    ),
    key = lambda x: x.timestamp,
)

# TODO: Process outages over time

with open('notable_outages.csv') as f:
    notable_outages = list(DictReader(f))

for outage in notable_outages:
    time_format = '%B %d %H:%M\'%Y'
    # TODO: Year handling is jank
    outage['outage_reported'] = datetime.strptime(
        outage['Outage Reported'] + str(datetime.now().year),
        time_format
    ) if outage['Outage Reported'] else None
    outage['estimated_time_of_restoration'] = datetime.strptime(
        outage['Estimated Time of Restoration'] + str(datetime.now().year),
        time_format
    ) if outage['Estimated Time of Restoration'] else None

# Graph
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

x, y_total, y_arecibo, y_bayamon, y_carolina, y_caguas, y_mayaguez, y_ponce, y_san_juan = (
    [x.timestamp for x in outage_timeseries],
    [x.total_clients_without_service for x in outage_timeseries],
    [x.arecibo_clients_without_service for x in outage_timeseries],
    [x.bayamon_clients_without_service for x in outage_timeseries],
    [x.carolina_clients_without_service for x in outage_timeseries],
    [x.caguas_clients_without_service for x in outage_timeseries],
    [x.mayaguez_clients_without_service for x in outage_timeseries],
    [x.ponce_clients_without_service for x in outage_timeseries],
    [x.san_juan_clients_without_service for x in outage_timeseries],
)

fig, ax = plt.subplots()

TIME_FORMAT = '%m/%d/%Y %H:%M'

ax.xaxis.set_major_formatter(mdates.DateFormatter(TIME_FORMAT))
ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=20))

OUTAGE_COLORS = {
    'Scheduled Maintenance': 'yellow',
    'Unplanned': 'red',
    '': 'grey',
}

OUTAGE_HATCHES = {
    'Scheduled Maintenance': r'\\',
    'Unplanned': r'//',
    '': r'\\\\',
}

# https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.axvspan.html#matplotlib.axes.Axes.axvspan
outage_polys = [
    ax.axvspan(
        outage['outage_reported'],
        outage['estimated_time_of_restoration'],
        alpha=0.3,
        color=OUTAGE_COLORS[outage['Category']],
        hatch=OUTAGE_HATCHES[outage['Category']]
    )
    for outage
    in notable_outages
    if outage['outage_reported'] and outage['estimated_time_of_restoration']
]

# https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.stackplot.html
ax.stackplot(x, y_arecibo, y_bayamon, y_carolina, y_caguas, y_mayaguez, y_ponce, y_san_juan, labels=REGIONS)

ax.set_title('LUMA Energy Customers Without Service By Region')
ax.set_xlabel('Datetime (EST)')
ax.set_ylabel('Customers Without Service')
fig.autofmt_xdate()
plt.legend(loc='best')

if interactive:
    import mplcursors

    scatter = ax.scatter(x, y_total)
    scatter_cursor = mplcursors.cursor(scatter)
    @scatter_cursor.connect('add')
    def on_add(sel: mplcursors.Selection):
        NEWLINE = '\n'
        moment = outage_timeseries[sel.index]
        sel.annotation.set_text(f"""Total: {moment.total_clients_without_service}
{NEWLINE.join(f'{region}: {getattr(moment, f"{normalize_name(region)}_clients_without_service")}' for region in REGIONS)}
Datetime: {moment.timestamp.strftime(TIME_FORMAT)}""")
        
    outages_cursor = mplcursors.cursor(outage_polys, hover=True)
    @outages_cursor.connect('add')
    def on_add(sel: mplcursors.Selection):
        outage = notable_outages[outage_polys.index(sel.artist)]
        sel.annotation.set_text(f"""Outage in {outage['Municipality'].title()}
Category: {outage['Category']}
Reported: {outage['outage_reported'].strftime(TIME_FORMAT)}
Estimated Restoration: {outage['estimated_time_of_restoration'].strftime(TIME_FORMAT)}
""")

    plt.show()
else:
    fig.set_size_inches(19.2, 10.8)
    fig.savefig('customers_without_service.png', dpi=100, bbox_inches='tight')
