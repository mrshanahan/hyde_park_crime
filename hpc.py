#!/usr/bin/env python
#########################################################################
# hpc.py
# @author: Matt Shanahan
#
# Accepts CSV files as command line args in the format taken from
# data.cityofchicago.org; parses files in chunks, then records statistics
# for various Chicagoland colleges and universities.  Default is number
# of incidents of crime on each campus per file (~ per year).  Results
# are displayed in a bar graph via pylab (matplotlib).
#
# Preferably, so labeling will work, CSV files should be named for their
# ranges: thus, a file for 2006 should be "data_2006.csv", one for
# 2004-2007 "data_2004-2007.csv", and one for all dates "data_all.csv".
#########################################################################
import sys, csv, urllib2, json, re

progname = sys.argv[0].split('/')[-1] # name of current program
READ_BLOCK = 500 # default number of lines to be read
# Google Maps API for geocoding
map_api_str = "http://maps.googleapis.com/maps/api/geocode/json?address={}&sensor=false"

# Get source file(s) 
if not sys.argv[1:]:
    source = "data/data_2011.csv"
else:
    sources = sys.argv[1:]

# Read in (block) lines of data from stream; returns (lines,True) if done parsing,
# and (lines,False) if there are still some lines left in the file
def read_in(block):
    lines = []
    for i in range(block):
        line = file_in.readline()
        if line != '':
            lines.append(line.strip())
        else: # end of data
            return (csv.reader(lines),True)
    return (csv.reader(lines),False)

# Grab data points according to user specification
def parse(data,grab=[]):
    # grab all items first
    reduced_data = dict(map(lambda x: (formatter[x],data[x]), range(len(formatter))))
    if grab != []: # if only getting certain values, restrict dict to those values
        tmp = reduced_data
        reduced_data = {}
        reduced_data = dict(filter(lambda x: x[0] in grab, tmp.items()))
    return reduced_data


# Object (with a few functions) to house various data points: name, boundaries, and
# statistics about the parsed crime data
class School(object):
    def __init__(self,name,(ne,sw)):
        self.name = name
        if type(ne) == str:
            ne = float(ne)
            sw = float(sw)
        self.ne = ne
        self.sw = sw
        self.data = {}

    # return True if given coordinate falls within campus, False otherwise
    def on_campus(self,loc):
        return loc[0] <= self.ne[0] and loc[0] >= self.sw[0] and \
               loc[1] <= self.ne[1] and loc[1] >= self.sw[1]

    # increments number of crimes for a certain year by one
    def incr_crime(self,year):
        self.data[year]['num_crimes'] += 1

# Returns a list of (ne,sw)
def get_coords(ne_address,sw_address):
    # grab coordinates using street addresses from Google Maps API (url at top)
    ne_req = urllib2.urlopen(map_api_str.format(ne_address.replace(' ','+')))
    ne_loc = json.loads(ne_req.read())['results'][0]['geometry']['location']
    sw_req = urllib2.urlopen(map_api_str.format(sw_address.replace(' ','+')))
    sw_loc = json.loads(sw_req.read())['results'][0]['geometry']['location']

    ne_req.close()
    sw_req.close()
  
    # convert to floating point; if fail, print out and exit
    try:
        ne = (float(ne_loc['lat']),float(ne_loc['lng']))
        sw = (float(sw_loc['lat']),float(sw_loc['lng']))
    except(KeyError):
        print "ne_loc:",ne_loc
        print "sw_loc:",sw_loc
        sys.exit(-1)

    return (ne,sw)

# Street addresses which (approximately) define the boundaries of the various campuses;
# clearly, this is not very exact, but it's the best option for now
uoc_ne = "5514 South University Ave, Chicago, IL"
uoc_sw = "6100 S Cottage Grove Ave, Chicago, IL"

uice_ne = "605 S Halsted St, Chicago, IL"
uice_sw = "1100 W 14th Pl, Chicago, IL"
#uicw_ne = "801 S Ashland Ave, Chicago, IL"
#uicw_sw = "2001 W Roosevelt Rd, Chicago, IL"

iit_ne = "3100 S Michigan Ave, Chicago, IL"
iit_sw = "3501 S La Salle St, Chicago, IL"

deploop_ne = "300 S Wabash Ave, Chicago, IL"
deploop_sw = "642 S State St, Chicago, IL"

schools = {"UoC": School("UChicago",get_coords(uoc_ne,uoc_sw)),
           "UIC": School("UIC East",get_coords(uice_ne,uice_sw)),
           "IIT": School("IIT",get_coords(iit_ne,iit_sw)),
           "DeP": School("DePaul Loop",get_coords(deploop_ne,deploop_sw))}

years = [] # list of years ("2006", "2007", etc., or "all") as taken from filenames
unknown_counter = 1 # counter if files are not correctly named

for source in sorted(sources):
    # first, check to see if file exists; if not, print error msg and continue to next
    try:
        file_in = open(source)
    except(IOError):
        print '%s: error: could not open file "%s"' % (progname, source)
        sys.exit(-1)

    # grab year from filename
    year_m = re.search("data_([a-zA-Z0-9\-]+)",source)
    if year_m is not None:
        year = year_m.group(1)
    else:
        year = "<unknown%s>" % unknown_counter
        unknown_counter += 1
    years.append(year)

    print 'Parsing file "{}"'.format(source.split('/')[-1])
    formatter = file_in.readline().strip().split(',') # formatting is in first line

    # initialize end of data marker and school info for current source
    endofdata = False
    for school in schools:
        schools[school].data[year] = {"num_crimes": 0, "crime_types": {}}

    # read from file until end of data marker is hit
    while not endofdata:
        csv_r,endofdata = read_in(READ_BLOCK)
        for row in csv_r:
            if row == []: continue # bad parse
            row_data = parse(row) # grab relevant data from row info

            # some entries simply do no have this data
            if row_data["Latitude"] == '' or row_data["Longitude"] == '':
                continue
            else:
                for school in schools:
                    # if crime occurred (approximately) on campus, mark it
                    if schools[school].on_campus((float(row_data["Latitude"]),float(row_data["Longitude"]))):
                        schools[school].incr_crime(year)
                        # record type of crime, too
                        if row_data["Primary Type"] not in schools[school].data[year]['crime_types'].keys():
                            schools[school].data[year]["crime_types"][row_data["Primary Type"]] = 1
                        else:
                            schools[school].data[year]["crime_types"][row_data["Primary Type"]] += 1

# Attempt to import pylab; this is not native, so it may not exist on every
# user's system, in which case we'll just do a default printing of the total
# occurrences of all types of crimes that occurred on each campus in the data set
try:
    from pylab import *
except(ImportError):
    print "%s: warning: could not import pylab; cannot graph data. Printing out plaintext.\n" % progname
    for s in schools.values():
        # print out name and boundary coordinates
        print "%s: NE (%f,%f), SW (%f,%f)" % (s.name,s.ne[0],s.ne[1],s.sw[0],s.sw[1])
        tmp_types = set(())
        # grab all primary types of crimes from all years
        for year in years:
            tmp_types.update(tuple(s.data[year]["crime_types"].keys()))
        tmp_types = list(tmp_types)
        tmp_occurrs = []
        # grab all occurrences of all types, and then make a map out of the two lists; this format
        # ensures that only crimes that have been recorded for that campus are displayed
        # (i.e. only positive integer results)
        for t in tmp_types:
            types_by_year = [s.data[y]["crime_types"] for y in years]
            tmp_occurrs.append(sum([year[t] for year in types_by_year if t in year.keys()]))
        tmp_map = dict([(tmp_types[i],tmp_occurrs[i]) for i in range(len(tmp_types))])
        # print out results
        for t in sorted(tmp_map.keys()):
            print "\t%s:%s%d" % (t,(35-len(t))*' ',tmp_map[t])
        print
    sys.exit(0)

# Graph results
print "Graphing data"
colors = ["red","blue","green","magenta","cyan","yellow","black","white"] # cycle through colors per school
years = sorted(years)
bar_width = 1.0/len(years) # bar width depends on number of files
for i in range(len(years)):
    year = years[i]
    offset = i*bar_width
    # draw graph
    bar(arange(len(schools))+offset,array([schools[x].data[year]['num_crimes'] for x in schools.keys()]),
        width=bar_width, label=year, color=colors[i%len(colors)])
xticks(arange(len(schools))+0.5, array([schools[x].name for x in schools.keys()]),)
title("Crimes committed on Chicago campuses")
legend()
show()
sys.exit(0)
