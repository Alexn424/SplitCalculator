from flask import Flask, render_template, request, redirect, send_from_directory
from zoneinfo import ZoneInfo
from fitparse import FitFile
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
import os
from zipfile import ZipFile
from split_calculators import distance_lap_calculator, time_lap_calculator

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
                save_path = zip_file.extract(member, app.config['UPLOAD_DIRECTORY'])
                run_data = parse_fit(save_path)
                return run_data

        os.remove(save_path)


@app.route('/')

def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])

def upload():
    try:
        lap_distance = 400
        lap_time = 60
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
            run_data = parse_fit(save_path)
            dlap_data = distance_lap_calculator(run_data, lap_distance)
            tlap_data, remainder_time = time_lap_calculator(run_data, lap_time)
        elif extension == '.zip': 
            safe_zip_name = secure_filename(uploaded_file.filename)
            save_path = os.path.join(app.config['UPLOAD_DIRECTORY'], safe_zip_name)
            uploaded_file.save(save_path)
            run_data = import_zip_file(save_path)
            if not run_data:
                return 'no fit files found in zip'
            dlap_data = distance_lap_calculator(run_data, lap_distance)
            tlap_data, remainder_time = time_lap_calculator(run_data, lap_time)
        return render_template('index.html', dlap_data=dlap_data, tlap_data=tlap_data, remainder_time=remainder_time)

    except RequestEntityTooLarge:
        return 'file exceeds 16MB limit'

if __name__ == '__main__':
    app.run(debug=True)   