#!/usr/bin/env python3
import json
import argparse
import sys
from collections import namedtuple
from datetime import datetime, date
import logging
from math import pow
from typing import List
import csv

__version__ = "0.1.0"

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

Location = namedtuple("Location", ["time", "point"])
Timeframe = namedtuple("Timeframe", ["start", "stop"])
Point = namedtuple("Point", ["lat", "long", "radius"])

TIMESTAMP_KEY = "timestampMs"
LATITUDE_KEY = "latitudeE7"
LONGITUDE_KEY = "longitudeE7"

SECONDS_PER_HOUR = 60 * 60


def maps_link(location: Point):
    """
    Generate a Google Maps link to a point
    """
    return f"https://www.google.com/search?hl=en&q={location.lat}%2C{location.long}"
    # return f"https://www.google.com/maps/@{location.lat},{location.long},15z"


def location_at_work(location: Point, work_points: List[Point]):
    """
    Is point within any of our work circles?
    """
    for point in work_points:
        # (x - center_x)^2 + (y - center_y)^2 < radius^2
        if pow(location.long - point.long, 2) + pow(location.lat - point.lat, 2) < pow(
            point.radius, 2
        ):
            return True

    return False


def location_in_timeframe(loc_time: int, times: List[Timeframe]):
    """
    Check if the given location is in an examined timeframe
    """
    for time in times:
        if time.start <= loc_time <= time.stop:
            return True

    return False


def main():
    logging.basicConfig(level=logging.DEBUG)

    parser = argparse.ArgumentParser(
        description="Look for location items in a given rectangle "
        "within a given timeframe and display the dates and minutes, along with"
        "a total of the time at that location."
    )
    parser.add_argument("json", help="path to location JSON file")
    parser.add_argument(
        "--area",
        help="Path to a file of latitude, longitude comma seperated pairs. Three or more should be given as a "
        "closed area to search in. Lines can be commented out with a leading '#'",
    )
    parser.add_argument(
        "--time",
        default=[],
        action="append",
        help="start,end comma separated timestamp in seconds."
        "Multiple may be specifed to allow multiple timeframes to apply or it may be left "
        "off accept all dates.",
    )
    parser.add_argument("-o", "--output", help="Output CSV of times to the given path")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    # Load up
    if args.debug:
        logger.setLevel(logging.DEBUG)

    logger.info("Opening points of interest from %s", args.area)
    work_points = []
    with open(args.area, "rb") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith(b"#"):
                continue

            lat, long, radius = [float(p.strip()) for p in line.split(b",")]
            work_points.append(Point(lat=lat, long=long, radius=radius))

    if not work_points:
        print("You must specify at least one point to look for as 'work'")
        return 1

    work_times = []
    for time_str in args.time:
        start, stop = [int(t) for t in time_str.split(",")]
        timeframe = Timeframe(start=start, stop=stop)
        logger.info(
            "Location times from %s to %s",
            datetime.fromtimestamp(timeframe.start),
            datetime.fromtimestamp(timeframe.stop),
        )
        work_times.append(timeframe)

    logger.info("Opening location JSON from %s", args.json)
    with open(args.json, "rb") as f:
        data = json.load(f)

    # Look for entry inside the search area in the specified time perdiod,
    # then count the time until we leave that area
    work_periods = []
    current_work_period = None
    for location in sorted(data["locations"], key=lambda loc: int(loc[TIMESTAMP_KEY])):
        # Simplify the location
        location = Location(
            time=int(location[TIMESTAMP_KEY]) // 1000,
            point=Point(
                lat=location[LATITUDE_KEY] / 10_000_000,
                long=location[LONGITUDE_KEY] / 10_000_000,
                radius=0,
            ),
        )
        when = datetime.fromtimestamp(location.time)

        # Are we at work at a reasonble time?
        if (
            location_in_timeframe(location.time, work_times) or not work_times
        ) and location_at_work(location.point, work_points):
            at_work = True
        else:
            at_work = False

        if at_work and not current_work_period:
            # Just got to work!
            current_work_period = Timeframe(start=location.time, stop=location.time)
            logger.debug("Got to work at %s (%s)", when, maps_link(location.point))
        elif at_work and current_work_period:
            # Extend workin time
            current_work_period = Timeframe(
                start=current_work_period.start, stop=location.time
            )
            # logger.debug("Still at work at %s (%s)", when, maps_link(location.point))
        elif not at_work and current_work_period:
            # Left work!
            current_work_period = Timeframe(
                start=current_work_period.start, stop=location.time
            )
            work_periods.append(current_work_period)

            if args.debug:
                seconds = current_work_period.stop - current_work_period.start
                when_from = datetime.fromtimestamp(current_work_period.start)
                when_to = datetime.fromtimestamp(current_work_period.stop)
                logger.debug(
                    f"Leaving work, worked for {seconds/SECONDS_PER_HOUR:.2f} hours, {when_from} to {when_to}. (went to %s)",
                    maps_link(location.point),
                )

            current_work_period = None

    if current_work_period:
        # History ended with us at work
        work_periods.append(current_work_period)
        logger.debug(
            "History ended with us at work: %s (last location %s)",
            current_work_period,
            maps_link(location.point),
        )
        current_work_period = None

    # Total up dates
    logger.info("Totaling dates")
    date_totals = {}
    for period in work_periods:
        when = date.fromtimestamp(period.start).strftime("%m/%d/%Y")
        seconds = period.stop - period.start
        date_totals[when] = seconds + date_totals.get(when, 0)

    date_totals = [(date_str, minutes) for date_str, minutes in date_totals.items()]

    if not args.output:
        total_seconds = 0
        for period in work_periods:
            when_from = datetime.fromtimestamp(period.start)
            when_to = datetime.fromtimestamp(period.stop)
            seconds = period.stop - period.start
            total_seconds += seconds

            print(
                f"{when_from} to {when_to}, {seconds/SECONDS_PER_HOUR:.2f} "
                f"hours (timestamp {period.start} seconds)"
            )

        print(f"Total time: {total_seconds/SECONDS_PER_HOUR:.2f} hours")
    else:
        logger.info("Writing CSV to %s", args.output)
        with open(args.output, "w") as f:
            sheet = csv.writer(f)
            sheet.writerow(["Date", "Seconds", "Hours"])

            for row in date_totals:
                sheet.writerow((row[0], row[1], row[1] / SECONDS_PER_HOUR))

    return 0


if __name__ == "__main__":
    sys.exit(main())
