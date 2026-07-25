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
    return render_template('index.html', dlap_info={}, tlap_info={})

@app.route('/upload', methods=['POST'])

def upload():
    try:
        lap_distance = request.form.get('lap_distance')
        lap_time = request.form.get('lap_time')

        run_dlap = lap_distance not in (None, '')
        run_tlap = lap_time not in (None, '')

        lap_distance = float(lap_distance) if run_dlap else 0
        lap_time = float(lap_time) if run_tlap else 0 


        dlap_info = {
            'dlap_data': [],
            'distance_remainder': None,
            'time_remainder': None,
            'lap_distances': [],
            'lap_confidence_scores': [],
            'avg_confidence': None
        }
        
        tlap_info = {
            'tlap_data': [],
            'remainder_distance': None,
            'lap_times': [],
            'remainder_time': None,
            'lap_confidence_scores': [],
            'avg_confidence': None
        }
                

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
            os.remove(save_path)
            if run_dlap:
                if 0 < lap_distance <= run_data[-1]['distance_m']:
                    dlap_info = distance_lap_calculator(run_data, lap_distance)
                else:
                    return 'Please enter a valid lap distance that is 0 < distance <= total distance (some watches underead total distance)'
            if run_tlap:
                total_time = run_data[-1]['timestamp_unix'] - run_data[0]['timestamp_unix']
                if 0 < lap_time <= total_time:
                    tlap_info = time_lap_calculator(run_data, lap_time)
                else:
                    return 'Please enter a valid lap time that is 0 < lap_time <= total distance'
        elif extension == '.zip': 
            safe_zip_name = secure_filename(uploaded_file.filename)
            save_path = os.path.join(app.config['UPLOAD_DIRECTORY'], safe_zip_name)
            uploaded_file.save(save_path)
            run_data = import_zip_file(save_path)
            if run_dlap:
                if 0 < lap_distance <= run_data[-1]['distance_m']:
                    dlap_info = distance_lap_calculator(run_data, lap_distance)
                else:
                    return 'Please enter a valid lap distance that is 0 < distance <= total distance (some watches underead total distance)'
            if run_tlap:
                total_time = run_data[-1]['timestamp_unix'] - run_data[0]['timestamp_unix']
                if 0 < lap_time <= total_time:
                   tlap_info = time_lap_calculator(run_data, lap_time)
                else:
                    return 'Please enter a valid lap time that is 0 < lap_time <= total distance'
       
        

        return render_template('index.html', dlap_info=dlap_info, tlap_info=tlap_info)

    except RequestEntityTooLarge:
        return 'file exceeds 16MB limit'

if __name__ == '__main__':
    app.run(debug=True)   