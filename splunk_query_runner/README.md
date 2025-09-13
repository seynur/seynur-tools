# Splunk Query Runner

The `splunk_query_runner` is a tool designed to automate the execution of queries from Splunk. It uses an input CSV file to specify the query parameters, connects to Splunk using either an authentication token (default) or user/password (additional modifications need to be made to this method.), and saves the query output in either CSV or JSON format.

## Table of Contents
1. [Files](#files)
2. [How It Works](#how-it-works)
3. [Running the Script](#running-the-script)
4. [Examples](#examples)

## Files

- **all_runner_script (bash script)**: This is the main script that starts the entire process. It prepares the environment, updates dates in input files, deletes old output files, and then runs the main Python script `splunk_query_runner.py`.
  
- **input_list.csv.example**: This file contains example queries and details for executing them in Splunk. The CSV includes fields for title, date, time, the SPL query, and the desired output format. You should implement this csv for your environment. 
  
- **splunk_query_runner.py (Python script)**: This script connects to Splunk, reads the queries from `input_list.csv.example`, and runs them. It supports various arguments such as the input file, Splunk hostname, port, and token information.
  
- **user.conf**: This file stores the authentication token or user/password details needed to authenticate with Splunk. Default option is Authentication Token. If user/password will be selected method, this can be changed on splunk_query_runner.py (uncomment 12 / 23-37 lines). In this case, you will see a command line where you can ask for the Splunk username and password for your security.
  
- **update_dates_for_input_files (bash script)**: This script automatically updates the start and end dates in the `input_list.csv` file to reflect yesterday and today, streamlining the automation process.
  
- **create_splunk_tokens**: This script helps generate Splunk authentication tokens for use in `splunk_query_runner.py`.

## How It Works

The entire process starts by running the `all_runner_script`. This script prepares the necessary environment, updates the input CSV file's dates, and deletes old output files. Once the environment is set up, it runs the Python script `splunk_query_runner.py`.

The Python script reads the queries from the `input_list.csv` file, establishes a connection to the Splunk instance (using either an authentication token or user credentials from `user.conf`), and runs the queries. The results are saved in the specified output format (CSV or JSON).

## Running the Script

1. **Ensure the environment is set up**: Make sure you have `bash`, `python3`, and Splunk installed. You should also configure the `user.conf` file with your Splunk authentication information.

2. **Run the `all_runner_script`**: This script will automatically handle all steps of the process. The steps include:
    - Creating an `outputs` directory.
    - Updating the `input_list.csv` file (or your desired file name) to reflect the current dates.
    - Running the `splunk_query_runner.py` script with the necessary arguments.

    ```bash
    ./all_runner_script
    ```

3. **Parameters for `splunk_query_runner.py`**:
   - `-i`: Input CSV file containing the queries.
   - `-sh`: Splunk hostname or IP (default: `localhost`).
   - `-sp`: Splunk management port (default: `8089`).
   - `-t`: Timestamp format representation for earliest and latest date and time (Default: `%d/%m/%Y %H:%M:%S`).
   - `-o`: Custom output path for results (Default: `''`).
   - `-s`: Internet protocol scheme (Default: `https`).
   - `-tk`: Authentication token file (default: `user.conf`).

!! Note: Please be sure, user.conf file is updated. As default, it contains <authentication_token> value.

## Examples

   - title : Static part of the output file name. The file will be naming as *"<title>-%d%m%YT%H%M%S_%d%m%YT%H%M%S.<file-format>"* and contains latest and earliest timestamps.
   - earliest_date : The earliest date (%d/%m/%Y) that the search will be run.
   - earliest_time : The earliest time (%H:%M:%S) that the search will be run.
   - latest_date : The latest date (%d/%m/%Y) that the search will be run.
   - latest_time : The latest time (%H:%M:%S) that the search will be run.
   - spl : The Splunk query that runs successfully on the Splunk UI.
   - output_format : The value will be the output format (CSV or JSON).
   - param : If there is a parametric timestamp as "%Y-%m-%d %H:%M:%S" format, this will be true. Otherwise, false.


Here’s an example of how the input CSV file (`input_list.csv.example`) looks like:

```csv
title;earliest_date;earliest_time;latest_date;latest_time;spl;output_format;param
EXAMPLE_internal;24/06/2024;10:00:00;24/06/2024;12:00:00;index=_internal | table host, log_level, sourcetype, _time | head  15;csv;false
EXAMPLE_savedsearch;01/06/2024;13:00:00;24/06/2024;14:00:00;| savedsearch "License Usage Data Cube";json;false
EXAMPLE_dbxquery;01/06/2024;13:00:00;24/06/2024;14:00:00;| dbxquery connection=<connection> query="SELECT date, time, msg FROM db_name.table_name WHERE STR_TO_DATE(CONCAT(date, ' ', time), '%Y-%m-%d %H:%i:%s') > ? ORDER BY date, time ASC" params="2024-11-12 17:05:39";csv;true
```

## Example Outputs on Terminal
```
STARTING ALL RUNNER SCRIPT

mkdir: outputs: File exists



Deleting old output files

rm: outputs/*: No such file or directory

Running splunk_query_runner.py



[{'earliest': 1728334800,
  'latest': 1728421200,
  'payload': {'earliest_time': 1728334800,
              'latest_time': 1728421200,
              'output_mode': 'csv',
              'search_mode': 'normal'},
  'spl': 'index=_internal | table host, log_level, sourcetype, _time | head  '
         '15',
  'title': 'EXAMPLE_internal'},
 {'earliest': 1728334800,
  'latest': 1728421200,
  'payload': {'earliest_time': 1728334800,
              'latest_time': 1728421200,
              'output_mode': 'json',
              'search_mode': 'normal'},
  'spl': '|tstats count where index=_internal by sourcetype | head 5',
  'title': 'EXAMPLE_tstats'},
 {'earliest': 1728334800,
  'latest': 1728421200,
  'payload': {'earliest_time': 1728334800,
              'latest_time': 1728421200,
              'output_mode': 'csv',
              'search_mode': 'normal'},
  'spl': 'index=nosuchindex',
  'title': 'EXAMPLE_empty'}]


8089    :   https    :   localhost


Splunk service created successfully
-----------------------------------
Running query for: EXAMPLE_internal_08102024T000000_09102024T000000.csv
Running query for: EXAMPLE_tstats_08102024T000000_09102024T000000.json
Running query for: X_EXAMPLE_empty_08102024T000000_09102024T000000.csv
```