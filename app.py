from flask import Flask, render_template, request, redirect, send_from_directory
from zoneinfo import ZoneInfo
from fitparse import FitFile
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
import os
from zipfile import ZipFile
import math

app = Flask(__name__)

app.config['MAX_CONTENT_LENGTH'] =  16 * 1024 * 1024
app.config['ALLOWED_EXTENSIONS'] = ['.fit', '.zip']
app.config['UPLOAD_DIRECTORY'] = 'uploads/'


def find_gps_change(long1, lat1, long2, lat2):
    change_in_long = (long2 - long1) * math.cos(lat1 * (math.pi / 2**31))
    change_in_lat = (lat2 - lat1)
    gps_change = math.atan2(change_in_lat, change_in_long)
    return gps_change


def distance_lap_calculator(run_records, lap_distance):
    lap_splits = []
    start_time = run_records[0]['timestamp_unix']
    end_time = run_records[-1]['timestamp_unix']
    curve_threshold = 0.02
    next_lap = lap_distance
    last_lap_time = start_time
    prev_second = None
    derived_distance = 0
    prev_derived = 0
    prev_gps_change = 0
    gps_change = 0
    gps_difference = 0
    curve_counter = 0
    straight_counter= 0
    for second in run_records:
        if second['position_lat'] is None:
            continue
        if second['position_long'] is None:
            continue
        if second['speed_mps'] is not None:
            prev_derived = derived_distance
            derived_distance += second['speed_mps']
        if prev_second is not None:
            if prev_second['position_lat'] is not None and prev_second['position_long'] is not None:
                lat1 = prev_second['position_lat']
                long1 = prev_second['position_long']
                lat2 = second['position_lat']
                long2 = second['position_long']
                gps_change = find_gps_change(long1, lat1, long2, lat2)
                if prev_gps_change != 0:
                    gps_difference = abs((gps_change - prev_gps_change))
                    if gps_difference > math.pi:
                        gps_difference = abs((gps_difference - (2 * math.pi)))
        if gps_difference < curve_threshold:
            straight_counter += 1         #solve for straight using gps
            if second['distance_m'] == next_lap:
                lap_splits.append(round(second['timestamp_unix'] - last_lap_time, 2))
                next_lap += lap_distance
                last_lap_time = second['timestamp_unix']
                prev_second = second
                prev_gps_change = gps_change
                continue
            elif second['distance_m'] > next_lap:
                if prev_second is None:
                    prev_second = second
                    next_lap += lap_distance
                    continue
                closing_speed = None
                if prev_second['speed_mps'] is not None:
                    closing_speed = prev_second['speed_mps']
                if closing_speed:
                    closing_distance = next_lap - prev_second['distance_m']
                    closing_time = closing_distance / closing_speed
                    lap_time = prev_second['timestamp_unix'] - last_lap_time
                    final_time = closing_time + lap_time
                    lap_splits.append(round(final_time, 2))
                    last_lap_time = prev_second['timestamp_unix'] + closing_time
                else:
                    lap_splits.append(round(second['timestamp_unix'] - last_lap_time, 2))
                    last_lap_time = second['timestamp_unix']
                next_lap += lap_distance
                prev_second = second
                prev_gps_change = gps_change
                continue
            else:
                prev_second = second
                prev_gps_change = gps_change
                continue
        else:
            curve_counter += 1
            if derived_distance == next_lap:
                lap_splits.append(round(second['timestamp_unix'] - last_lap_time, 2))
                next_lap += lap_distance
                last_lap_time = second['timestamp_unix']
                prev_second = second
                prev_gps_change = gps_change
                continue
            elif derived_distance > next_lap:
                if prev_second is None:
                    prev_second = second
                    next_lap += lap_distance
                    continue
                closing_speed = None
                if prev_second['speed_mps'] is not None:
                    closing_speed = prev_second['speed_mps']
                if closing_speed:
                    closing_distance = next_lap - prev_derived
                    closing_time = closing_distance / closing_speed
                    lap_time = prev_second['timestamp_unix'] - last_lap_time
                    final_time = closing_time + lap_time
                    lap_splits.append(round(final_time, 2))
                    last_lap_time = prev_second['timestamp_unix'] + closing_time
                else:
                    lap_splits.append(round(second['timestamp_unix'] - last_lap_time, 2))
                    last_lap_time = second['timestamp_unix']
                next_lap += lap_distance
                prev_second = second
                prev_gps_change = gps_change
                continue
            else:
                prev_second = second
                prev_gps_change = gps_change
                continue
    if last_lap_time < end_time:
        remainder = end_time - last_lap_time
        lap_splits.append(round(remainder, 2))
    distance = run_records[-1]['distance_m']
    print(derived_distance)
    print(distance)
    print(curve_counter, straight_counter)
    return lap_splits

def time_lap_calculator(run_records, lap_time):
    start_time = run_records[0]['timestamp_unix']
    end_time = run_records[-1]['timestamp_unix']
    lap_distances = []
    next_lap = lap_time
    prev_distance = 0
    last_lap_time = None
    remainder_time = None
    for second in run_records:
        if second['timestamp_unix'] - start_time >= next_lap:
            distance = second['distance_m']
            window_distance = distance - prev_distance 
            lap_distances.append(round(window_distance, 2))
            prev_distance = distance
            next_lap += lap_time
            last_lap_time = second['timestamp_unix']
    if prev_distance < run_records[-1]['distance_m']:
        remainder = run_records[-1]['distance_m'] - prev_distance
        remainder_time = end_time - last_lap_time
        lap_distances.append(round(remainder, 2))

    return lap_distances, remainder_time

def parse_fit(save_path):
    fit_file = FitFile(save_path)
    record_data = []
    for msg in fit_file.get_messages('record'):
        record_run = {f.name: f.value for f in msg}
        if record_run.get('timestamp') is None:
            continue
        timestamp = record_run.get('timestamp')
        utc_dt = timestamp.replace(tzinfo=ZoneInfo('UTC'))
        la_dt = utc_dt.astimezone(ZoneInfo('America/Los_Angeles'))
        timestamp_dt = la_dt.timestamp()

        clean_record = {
            'timestamp_unix': timestamp_dt,
            'distance_m': record_run.get('distance'),
            'heart_rate': record_run.get('heart_rate'),
            'speed_mps': record_run.get('enhanced_speed') or record_run.get('speed'),
            'position_lat': record_run.get('position_lat'),
            'position_long': record_run.get('position_long'),
            'cadence_spm': record_run.get('cadence'),
            'gct_ms': record_run.get('stance_time'),
            'vert_oscillation': record_run.get('vertical_oscillation'),
            'vert_ratio': record_run.get('vertical_ratio'),
            'power': record_run.get('power'),
            'altitude': record_run.get('enhanced_altitude') or record_run.get('altitude')
        }
        record_data.append(clean_record)
    return record_data

def import_zip_file(save_path):  
    with ZipFile(save_path, 'r') as zip_file:
        
        for member in zip_file.namelist():

            file_extension = os.path.splitext(member)[1].lower()
            
            if file_extension == '.fit':
                name = os.path.basename(member)
                safe_file_name = secure_filename(name)
                return safe_file_name

        os.remove(save_path)

def distance_lap(run_data, lap_distance):
    lap_splits = []
    start_time = run_data[0]['timestamp_unix']
    end_time = run_data[-1]['timestamp_unix']
    next_lap = lap_distance
    last_lap_time = start_time
    previous_second = None
    for second in run_data:
        if second['distance_m'] == next_lap:
            lap_splits.append(second['timestamp_unix'] - last_lap_time)
            next_lap += lap_distance
            last_lap_time = second['timestamp_unix']
            previous_second = second
            continue
        elif second['distance_m'] > next_lap:
            if previous_second is None:
                previous_second = second
                continue
            closing_speed = previous_second['speed_mps']
            if closing_speed:
                closing_distance = next_lap - previous_second['distance_m']
                closing_time = closing_distance / closing_speed
                lap_time = previous_second['timestamp_unix'] - last_lap_time
                final_time = closing_time + lap_time
                lap_splits.append(round(final_time, 2))
                next_lap += lap_distance
                last_lap_time = previous_second['timestamp_unix'] + closing_time
            previous_second = second
        else:
            continue
    if last_lap_time < end_time:
        remainder = end_time - last_lap_time
        lap_splits.append(round(remainder, 2))
    return lap_splits


@app.route('/')

def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])

def upload():
    try:
        lap_distance = 400
        uploaded_file = request.files.get('file') 
        if uploaded_file is None or uploaded_file.filename == '' :
            return redirect('/')
        extension = os.path.splitext(uploaded_file.filename)[1].lower()

        if extension not in app.config['ALLOWED_EXTENSIONS']:
            return 'Invalid file type'
        
        if extension == '.fit': 
            safe_name = secure_filename(uploaded_file.filename)
            save_path = os.path.join(app.config['UPLOAD_DIRECTORY'], safe_name)
            uploaded_file.save(save_path)
            run_data = parse_fit(path)
            dlap_data = distance_lap_calculator(run_data, lap_distance)

        elif extension == '.zip': 
            safe_zip_name = secure_filename(uploaded_file.filename)
            save_path = os.path.join(app.config['UPLOAD_DIRECTORY'], safe_zip_name)
            safe_file_name = import_zip_file(save_path)
            if not safe_file_name:
                return 'no fit file detected'
            path = os.path.join(app.config['UPLOAD_DIRECTORY'], safe_file_name)
            uploaded_file.save(path)
            run_data = parse_fit(path)
            dlap_data = distance_lap_calculator(run_data, lap_distance)
        return render_template('index.html', dlap_data)

    except RequestEntityTooLarge:
        return 'file exceeds 16MB limit'

if __name__ == '__main__':
    app.run(debug=True)   