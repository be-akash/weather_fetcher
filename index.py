from flask import Flask, render_template, request, jsonify, send_file
import os

# We are not sharing our amazon credentials to git repository. That's why user's need to rename the file name. Here
# check if the file "amazon_credentials.py" exists and import the credentials if it does otherwise import the default
if os.path.isfile("amazon_credentials.py"):
    from amazon_credentials import access_key_id, secret_access_key, Region
else:
    access_key_id = "access_key_id"
    secret_access_key = "secret_access_key"
    Region = "Region"
import csv
import time
import threading
import datetime
import requests
import boto3

app = Flask(__name__)

# Open Meteo Default API URL
API_URL = "https://api.open-meteo.com/v1/forecast"
# Location coordinates of Cologne City
LATITUDE = 50.93
LONGITUDE = 6.95
# Default Interval Values. Here We set 60 secs by default
INTERVAL = 30*60  # Interval in seconds (e.g., 3600 for 1 hour)
# Flag indicating if Amazon AWS credentials are available
amazon_flag = False

# Create an S3 Client using the credentials
s3 = boto3.client('s3', aws_access_key_id=access_key_id,
                  aws_secret_access_key=secret_access_key,
                  region_name=Region)

# Here We are testing the S3 connection if the credentials are authentic or not.
try:
    response = s3.list_buckets()
    print("Connection to S3 successful. Buckets:")
    for bucket in response['Buckets']:
        a = bucket['Name']
        print("Bucket Name")
    amazon_flag = True
except Exception as e:
    amazon_flag = False
    print("An error occurred:", str(e))


# Function to retrieve current weather data from Open-Meteo API
def get_current_weather_data():
    print("INTERVAL:" + str(INTERVAL))
    url = f"{API_URL}?latitude={LATITUDE}&longitude={LONGITUDE}"
    params = {
        "current_weather": "true",
        "hourly": "rain,showers,visibility,temperature_2m",
        "timezone": "Europe/Berlin",
        "forecast_days": 1
    }
    print(url)
    response = requests.get(url, params)
    print(response)
    if response.status_code == 200:
        return response.json()
    else:
        print("Failed to retrieve current weather data.")
        return None


# Function to write weather data to a CSV File
def write_to_csv(data):
    if data:
        current_timestamp = time.time()
        filename = "csv/cologne_current_weather_" + str(current_timestamp) + ".csv"
        print(filename)
        with open(filename, mode='w', newline='') as file:
            writer = csv.writer(file)
            current_weather = data['current_weather']
            print(current_weather['time'])
            for key in data:
                if type(data[key]) is not dict:
                    writer.writerow([key, data[key]])
                else:
                    writer.writerow([key])
                    for values in data[key]:
                        if type(data[key][values]) is not list:
                            writer.writerow([values, data[key][values]])
                    if key == "hourly":
                        keys = data[key].keys()
                        keys = list(keys)
                        print()
                        print(keys)
                        for i in range(len(data[key][keys[0]])):
                            writer.writerow(
                                [data[key][keys[0]][i], data[key][keys[1]][i], data[key][keys[2]][i],
                                 data[key][keys[3]][i],
                                 data[key][keys[4]][i]])

            print(f"Current weather data successfully written to {filename}.")
        return filename
    else:
        print("No weather data available to write to CSV.")


# Function to continusosly fetch weather data in a separate Thread
def fetch_weather_data():
    global weather_data
    global INTERVAL
    global amazon_flag
    # global s3
    while True:
        print("Hello I am printing CSV")
        current_weather_data = get_current_weather_data()
        if current_weather_data:
            current_datetime = datetime.datetime.now()
            formatted_datetime = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
            filename = write_to_csv(current_weather_data)
            bucket_name = "fraunhoferinterview"
            file_name = filename
            destination_folder = "data/" + filename
            if amazon_flag:
                s3.upload_file(file_name, bucket_name, destination_folder)
            else:
                current_weather_data['amazon_flag'] = amazon_flag
            print("**********************")
            print("INTERVAL" + str(INTERVAL))
            print("Uploaded to amazon aws")
            print("**********************")
            current_weather_data['last_update_time'] = formatted_datetime

            weather_data = current_weather_data
            print(weather_data)
        time.sleep(INTERVAL)


# Route for the home page with the current weather data. If there is no weather data it will return appropriate
@app.route('/', methods=['GET', 'POST'])
def index():
    try:
        print("INTERVAL" + str(INTERVAL))
        return render_template('index.html', weather_data=weather_data)
    except NameError:
        print("Hello")
        return render_template('index.html')


# Route for updating the data fetch Interval. It will update the global variable Interval.
@app.route('/update_interval', methods=['GET'])
def update_interval():
    global INTERVAL  # Access the global variable
    interval_hour = int(request.args.get('intervalHour'))
    interval_minutes = int(request.args.get('intervalMinutes'))
    INTERVAL = (interval_hour * 60 + interval_minutes) * 60  # Convert hours and minutes to seconds
    print("INTERVAL" + str(INTERVAL))
    interval_msg = "Update Interval time will be : " + str(interval_hour) + " hours and " + str(
        interval_minutes) + " minutes";
    return jsonify({'status': interval_msg})


# Route for getting a list of all files in the 'csv' folder
@app.route('/get_allfiles', methods=['GET'])
def get_allfiles():
    try:
        # Get a list of all files in the folder
        files = os.listdir('csv')
        response = {'files': files}
        status_code = 200
    except Exception as e:
        response = {'error': str(e)}
        status_code = 500
    print("Hello")
    return jsonify(response), status_code


# Route for downloading the csv file
@app.route('/download', methods=['GET'])
def download():
    fileName = request.args.get('filename')
    print(fileName)
    return send_file('csv/' + fileName, as_attachment=True)
    # return jsonify({'status': 'success'})


# Route for deleteing the a file from the 'csv' Folder
@app.route('/delete', methods=['GET'])
def delete():
    fileName = request.args.get('filename')
    try:
        os.remove('csv/' + fileName)
    except Exception as e:
        print("File Deleted")
    try:
        # Get a list of all files in the folder
        files = os.listdir('csv')
        response = {'files': files}
        status_code = 200
    except Exception as e:
        response = {'error': str(e)}
        status_code = 500
    return jsonify(response), status_code


# Main Entry point of the application
if __name__ == '__main__':
    if not os.path.exists('csv'):
        os.makedirs('csv')
    else:
        print("Folder Already Exists")
    # Start a separate thread for fetching weather data
    weather_thread = threading.Thread(target=fetch_weather_data)
    weather_thread.daemon = True
    weather_thread.start()
    # Run the Flask application on port 5000
    app.run(host='0.0.0.0', port=5000)
