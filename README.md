# location-history-total
Given a Takeout of Google Location History, generate a CSV of work history.

Requires Python 3.6+.

# Example usage

1. Create a document with your points of interest:

    ```
    # Format is lat, long, radius
    # '#' can be used to comment a line out
    38.8100121,-104.6792472, 0.04
    39.1355552,-121.3484781, 0.1
    ```

    Google Maps will be handy for determining the latitude and longitude of places.

2. Use Google Takeout to export your location history.

   - Current link is https://takeout.google.com/settings/takeout?hl=en
   - Support link is https://support.google.com/accounts/answer/3024190?hl=en

3. (Optional) Determine the time period(s) you're intested in and get the Unix timestamps of the start and stop dates.

3. Run the script. Assuming your POIs are in `area.txt`, your location history is at `history.json`, and a date range of 1 Oct 2018-1 Mar 2019:

    ```
    # Dump information to screen
    location-history-total history.json --area=area.txt --time=1538373600,1551423600

    # Or to a CSV
    location-history-total history.json --area=area.txt --time=1538373600,1551423600 --output=results.csv
    ```


