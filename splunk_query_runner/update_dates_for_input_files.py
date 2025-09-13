from datetime import datetime, timedelta

# File paths
file_paths = ["input_list.csv"]

# Calculate earliest & latest date
earliest_date = (datetime.now() - timedelta(days=1)).strftime("%d/%m/%Y")
earliest_time = "00:00:00"
latest_date = datetime.now().strftime("%d/%m/%Y")
latest_time = "00:00:00"

for file_path in file_paths:
    # Read the file and process the data
    with open(file_path, 'r') as file:
        lines = file.readlines()

    header = lines[0].strip()  # first line is the header 
    data = []

    # Delete after first line
    for line in lines[1:]:
        parts = line.strip().split(';')
        title, spl, output_format, param = parts[0], parts[5], parts[6], parts[7]

        if param == "true":
            checkpoint_timestamp = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
            spl = spl[0:spl.find('params="') + len('params=')] + f'"{checkpoint_timestamp}"'
        # Update data with new date values
        data.append(f"{title};{earliest_date};{earliest_time};{latest_date};{latest_time};{spl};{output_format};{param}")

    # Rewrite the file
    with open(file_path, 'w') as file:
        file.write(f"{header}\n")  # Header line
        file.write("\n".join(data))  # Updated data