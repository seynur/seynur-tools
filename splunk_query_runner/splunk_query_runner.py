import splunklib.client as client
import getpass
import csv
import json
import time
import sys
import argparse
from pprint import pprint

def connect_to_splunk(host='localhost', port='8089', scheme='https', token_name='user.conf'):
    """Returns splunk_service object. Connects to a Splunk instance."""
    #method = input('Which creadential method will be used? 1: Token, 2 User/Password: ')

    try:
        with open(token_name) as csvfile:
            token=csvfile.read().replace("\n","")

        splunk_service = client.connect(
            host=host, port=port, token=token, scheme=scheme
        )
        

        #if method == '1':
        #    with open(token_name) as csvfile:
        #        token=csvfile.read().replace("\n","")

        #    splunk_service = client.connect(
        #        host=host, port=port, token=token, scheme=scheme
        #    )
        #else:
        #    username = input('Enter your username: ')
        #    password = getpass.getpass('Enter your password: ')

        #    splunk_service = client.connect(
        #        host=host, port=port, username=username, password=password,
        #        scheme=scheme
        #    )
        
        print("\n")
        print("Splunk service created successfully")
        print("-----------------------------------")
        return splunk_service
    except Exception as e:
        print(f"Error connecting to Splunk: {e}")
        sys.exit(1)

def read_csv(search_csv, timestamp_format):
    """Reads input CSV file and returns an array of search dictionaries."""
    searches = []
    try:
        with open(search_csv, newline='') as csvfile:
            csvreader = csv.DictReader(csvfile, delimiter=';')
            for row in csvreader:
                tmp_earliest = int(time.mktime(time.strptime(f"{row['earliest_date']} {row['earliest_time']}", timestamp_format)))
                tmp_latest = int(time.mktime(time.strptime(f"{row['latest_date']} {row['latest_time']}", timestamp_format)))
                searches.append({
                    "title": row['title'],
                    "spl": row['spl'],
                    "earliest": tmp_earliest,
                    "latest": tmp_latest,
                    "payload": {
                        "earliest_time": tmp_earliest,
                        "latest_time": tmp_latest,
                        "search_mode": "normal",
                        "output_mode": row['output_format']
                    }
                })
        print("\n")
        pprint(searches)
        print("\n")
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        sys.exit(1)
    return searches

def run_search(splunk_service, searches, output_path_custom):
    """Runs the Splunk searches and converts results to files based on the specified output format."""
    try:
        for search in searches:
            output_file = f"{search['title']}_{time.strftime('%d%m%YT%H%M%S', time.localtime(search['earliest']))}_{time.strftime('%d%m%YT%H%M%S', time.localtime(search['latest']))}.{search['payload']['output_mode']}"
            oneshot_search_query = search['spl'] if search['spl'].startswith(("|dbxquery", "| dbxquery", "| tstats", "|tstats", "|savedsearch", "| savedsearch")) else f"search {search['spl']}"
            result = splunk_service.jobs.oneshot(oneshot_search_query, **search['payload']).read()
            output_file = f"X_{output_file}" if len(result) < 2 else f"{output_file}"

            print(f"Running query for: {output_file}")
            output_path = f"{output_path_custom}/{output_file}" if output_path_custom!="" else f"{output_file}"

            if search['payload']['output_mode'] == 'json':
                result_json = json.loads(result)
                
                with open(output_path, 'w') as f:
                    json.dump(result_json["results"], f, indent=4)
            else:
                with open(output_path, 'wb') as f:
                    f.write(result.strip())

    except Exception as e:
        print(f"Error running search: {e}")
        sys.exit(1)

def get_args(script_name):
    """Parses command line arguments."""
    
    # Helper text providing example usage of the script
    helper_text = ''' Example:
    $> cat input_list.csv
    title;earliest_date;earliest_time;latest_date;latest_time;spl;output_format
    EXAMPLE_internal;24/06/2024;10:00:00;24/06/2024;12:00:00;index=_internal | table host, log_level, sourcetype, _time | head  15;csv
    EXAMPLE_savedsearch;01/06/2024;13:00:00;24/06/2024;14:00:00;| savedsearch "License Usage Data Cube";json

    $> python3 audit_query_runner.py -h localhost -i input_list.csv
    ...

    $> cat input_list.csv
    title;earliest_date;earliest_time;latest_date;latest_time;spl;output_format
    EXAMPLE_internal;24.06.2024;10:00:00;24.06.2024;12:00:00;index=_internal | table host, log_level, sourcetype, _time | head  15;json
    EXAMPLE_savedsearch;01.06.2024;13:00:00;24.06.2024;14:00:00;| savedsearch "License Usage Data Cube";json

    $> python3 audit_query_runner.py -h 192.168.1.100 -i otherinput.csv -t "%d.%m.%Y %H:%M:%S" -o output_path_location
    ...
    '''
    
    # Initialize the argument parser with the script name and helper text
    parser = argparse.ArgumentParser(epilog=helper_text, formatter_class=argparse.RawTextHelpFormatter, prog=script_name)
    
    # Add argument for input CSV file
    parser.add_argument(
        "-i", "--input-file", 
        type=str, 
        required=True, 
        help="Csv file with the following format: title;earliest_date;earliest_time;latest_date;latest_time;spl;output_format"
    )
    
    # Add argument for Splunk hostname or IP address
    parser.add_argument(
        "-sh", "--splunk-host", 
        type=str, 
        default="localhost", 
        help="Splunk hostname or IP address (Default: localhost)."
    )
    
    # Add argument for Splunk managment port
    parser.add_argument(
        "-sp", "--splunk-managment-port", 
        type=str, 
        default="8089", 
        help="Splunk managment port (Default: 8089)."
    )   

    # Add argument for timestamp format representation
    parser.add_argument(
        "-t", "--timestamp-format", 
        type=str, 
        default="%d/%m/%Y %H:%M:%S", 
        help="Timestamp format representation for earliest and latest date and time (Default: %d/%m/%Y %H:%M:%S)."
    )
    
    # Add argument for custom output path for results
    parser.add_argument(
        "-o", "--output-path", 
        type=str, 
        default="", 
        help="Custom output path for results (Default: '')."
    )

    # Add argument for internet protocol scheme
    parser.add_argument(
        "-s", "--splunk-scheme", 
        type=str, 
        default="https", 
        help="Internet protocol scheme (Default: https)."
    )   

    # Add argument for token name
    parser.add_argument(
        "-tk", "--token_name", 
        type=str, 
        default="user.conf", 
        help="Token file name for Splunk (Default: user.conf)."
    )   
    # Parse and return the command line arguments
    return parser.parse_args()

def main():
    try:
        args = get_args(sys.argv[0])
        searches = read_csv(args.input_file, args.timestamp_format)
        print(args.splunk_managment_port, "   :  ", args.splunk_scheme, "   :  ", args.splunk_host)
        splunk_service = connect_to_splunk(host=args.splunk_host, port=args.splunk_managment_port, scheme=args.splunk_scheme, token_name=args.token_name)
        run_search(splunk_service, searches, args.output_path)
    except Exception as e:
        print(f"Error in main: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()