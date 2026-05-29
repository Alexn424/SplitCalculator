from flask import Flask, render_template, request, redirect, send_from_directory
from zoneinfo import ZoneInfo
from fitparse import FitFile
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
import os
from zipfile import ZipFile

app = Flask(__name__)

app.config['MAX_CONTENT_LENGTH'] =  16 * 1024 * 1024
app.config['ALLOWED_EXTENSIONS'] = ['.fit', '.zip']
app.config['UPLOAD_DIRECTORY'] = 'uploads/'

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
                path = zip_file.extract(member, app.config['UPLOAD_DIRECTORY'])
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

        elif extension == '.zip': 
            safe_zip_name = secure_filename(uploaded_file.filename)
            save_path = os.path.join(app.config['UPLOAD_DIRECTORY'], safe_zip_name)
            safe_file_name= import_zip_file(save_path)
            if not safe_file_name:
                return 'no fit file detected'
            path = os.path.join(app.config['UPLOAD_DIRECTORY'], safe_file_name)
            uploaded_file.save(path)
            run_data = parse_fit(path)

    except RequestEntityTooLarge:
        return 'file exceeds 16MB limit'

if __name__ == '__main__':
    app.run(debug=True)   