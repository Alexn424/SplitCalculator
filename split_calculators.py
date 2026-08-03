import math
import numpy as np
from scipy.optimize import curve_fit
from collections import deque
import matplotlib.pyplot as plt

def find_gps_bearing(lat1, long1, lat2, long2):
    conversion = math.pi / 2**31
    lat1_rads = lat1 * conversion
    long1_rads = long1 * conversion
    lat2_rads = lat2 * conversion
    long2_rads = long2 * conversion

    delta_long = long2_rads - long1_rads
    x = math.sin(delta_long) * math.cos(lat2_rads)
    y = math.cos(lat1_rads) * math.sin(lat2_rads) - math.sin(lat1_rads) * math.cos(lat2_rads) * math.cos(delta_long)    
    gps_bearing = math.atan2(x,y)

    return gps_bearing

def find_angle_diff(heading1, heading2):
    angle_difference = heading2 - heading1

    if angle_difference > math.pi:
        angle_difference -= 2 * (math.pi)

    elif angle_difference < -1 * (math.pi):
        angle_difference += 2 * (math.pi)

    return angle_difference

def state_machine(gps_diff, state, momentum, blend_weight):
    current_state = state
    low_threshold = 0.03
    high_threshold = 0.1
    c_blend_weight = blend_weight
    c_blend_weight = max(0, min(1, c_blend_weight))
    cur_threshold = 3
    str_threshold = -5
    curve_count = 0
    straight_count = 0
    angle_diff = abs(gps_diff)


    if current_state == 'straight':
        if angle_diff <= low_threshold:
            momentum -= 1
            momentum = max(-5, min(3, momentum))
        
        elif low_threshold < angle_diff < high_threshold:
            current_state = 'blended'
        
        elif high_threshold <= angle_diff:
            current_state = 'blended'
            momentum += 1
            momentum = max(-5, min(3, momentum))

    elif current_state == 'curved':
        if angle_diff <= low_threshold:
            current_state = 'blended'
            momentum -= 1
            momentum = max(-5, min(3, momentum))
        
        elif low_threshold < angle_diff < high_threshold:
            current_state = 'blended'
        
        elif high_threshold <= angle_diff:
            momentum += 1
            momentum = max(-5, min(3, momentum))

    elif current_state == 'blended':
        
        if angle_diff <= low_threshold:
            momentum -= 1
            c_blend_weight -= 0.2
            c_blend_weight = max(0, min(1, c_blend_weight))
            momentum = max(-5, min(3, momentum))
            if momentum == str_threshold:
                current_state = 'straight'
                straight_count += 1
                c_blend_weight = 0
        
        elif low_threshold < angle_diff < high_threshold:
            current_state = 'blended'
        
        elif high_threshold <= angle_diff:
            momentum += 1
            c_blend_weight += 0.33
            c_blend_weight = max(0, min(1, c_blend_weight))
            momentum = max(-5, min(3, momentum))
            if momentum == cur_threshold:
                current_state = 'curved'
                curve_count += 1
                c_blend_weight = 1

    #print(f'straight count: {straight_count}')
    #print(f'curve_count: {curve_count}')
    #print('blend_weight', c_blend_weight)
    #print('state', state)
    #print('momentum', momentum)
    #print('angle_diff', angle_diff)
        
    return current_state, momentum, c_blend_weight

def sine_wave(x, A, period, phase, midline):
    #proof of concept for now but might use fourier series later for improved accuracy
    return A * np.sin(2 * np.pi * x / period + phase) + midline

def normalize_data(run_data, x, y, lap_distance):
    x_vals = []
    y_vals = []
    x_temp = []
    y_temp = []

    lap_count = 0
    lap_boundary = lap_distance

    for h in run_data:
        if h[y] and h[x] and h[x] < lap_boundary:
            x_point = h[x] - (lap_distance * lap_count)
            x_temp.append(x_point)
            y_temp.append(h[y])
        else:
            x_vals.append(np.array(x_temp))
            y_vals.append(np.array(y_temp))
            x_temp = [h[x] - lap_distance]
            y_temp = [h[y]]
            lap_boundary += lap_distance
            lap_count += 1

    x_all = np.concatenate(x_vals)
    y_all = np.concatenate(y_vals)

    sort_order = np.argsort(x_all)
    x_all = x_all[sort_order]
    y_all = y_all[sort_order]

    standard_rate = np.mean(np.diff(x_all))
    x_normalized = np.arange(0, lap_distance, standard_rate)

    y_interp = np.interp(x_normalized, x_all, y_all)

    return x_normalized, y_interp

def estimate_fourier_params(run_data, x, y, lap_distance, harmony_num):
    x_normalized, y_interp = normalize_data(run_data, x, y, lap_distance)

    design_matrix = []

    for i in range(1, harmony_num + 1):
        sin_basis = np.sin(i * x_normalized * 2 * np.pi / lap_distance)
        cos_basis = np.cos(i * x_normalized * 2 * np.pi / lap_distance)
        design_matrix.append(sin_basis)
        design_matrix.append(cos_basis)

    design_matrix = np.column_stack(design_matrix)
    bias = np.ones((x_normalized.shape[0], 1))
    design_with_bias = np.hstack([design_matrix, bias])

    weights, _, _, _ = np.linalg.lstsq(design_with_bias, y_interp)

    return weights

def fourier_wave(x, lap_distance, weights):
    harmony_num = int((len(weights) - 1) / 2)
    parts = []
    for h in range(1, harmony_num + 1):
        parts.append(np.sin(h * x * 2 * np.pi / lap_distance ) * weights[2 * (h - 1)])
        parts.append(np.cos(h * x * 2 * np.pi / lap_distance) * weights[2 * (h - 1) + 1])

    output = np.sum(parts, axis=0) + weights[-1]

    return output


def estimate_sine_params(run_data, x, y):
    x_vals = []
    y_vals = []
    for h in run_data:
        if h[y] and h[x]:
            x_vals.append(h[x])
            y_vals.append(h[y]) 

    midline = sum(y_vals) / len(y_vals)
    top_percentile = np.percentile(y_vals, 99.5)
    bottom_percentile = np.percentile(y_vals, 0.5)
    amplitude = (top_percentile - bottom_percentile) / 2
    prev_prev = None
    prev = None
    y_peaks = []
    peak_index = []
    for a, b in enumerate(y_vals):
        if prev_prev is None and prev is None:
            prev_prev = b
            continue
        elif prev is None:
            prev = b
            continue
        if prev_prev < prev and b < prev:
            y_peaks.append(prev)
            peak_index.append(a)
        prev_prev = prev
        prev = b
    x_peaks = []
    for i in peak_index:
        x_peaks.append(x_vals[i])

    peak_differences = []
    prev_peak = None    
    for d in x_peaks:
        if prev_peak is None:
            prev_peak = d
            continue
        peak_differences.append(d - prev_peak)
        prev_peak = d
    period = sum(peak_differences) / len(peak_differences)
    phase = (((2 * np.pi) * x_peaks[0]) / period) - (np.pi / 2)

    x_array = np.array(x_vals)
    y_array = np.array(y_vals)
    params, _ = curve_fit(sine_wave, x_array, y_array, p0=[amplitude, period, phase, midline])

    return params


def find_confidence_score(timestamp_gaps, distance_spikes, bearing_anomalies,
                            record_inconsistency, lat_rsme, long_rsme):
    bearing_penalty = max(0, bearing_anomalies -1 )
    confidence_score = (100 - (bearing_penalty * 5) - min(20, (distance_spikes * 12)) - (timestamp_gaps * 2) 
                        - (record_inconsistency * 15))
    confidence_score = max(0, confidence_score)
    return confidence_score

def distance_lap_calculator(run_records, lap_distance, mode='road'):
    lap_splits = []
    start_time = run_records[0]['timestamp_unix']
    end_time = run_records[-1]['timestamp_unix']
    lap_distances = []
    next_lap = lap_distance
    last_lap_time = 0
    prev_second = None
    derived_distance = 0
    prev_change = 0
    state = 'straight'
    blend_weight = 0
    momentum = 0
    blended_distance = 0
    lap_count = 0
    prev_blended = None

    #confidence score related stuff
    confidence_scores = []
    lap_confidence_scores = []
    confidence_score = 0
    timestamp_gaps = 0
    distance_spikes = 0
    rolling_distance = deque(maxlen=int(round(max(5, lap_distance * 0.02))))
    distance_avg = 0
    bearing_anomaly_threshold = 0.55
    bearing_anomalies = 0
    lap_record_count = 0
    record_inconsistency = 0
    remainder_penalty = 0

    #specific to track mode
    lat_residuals = []
    long_residuals = []
    lat_rsme = 0
    long_rsme = 0

    lat_weights = estimate_fourier_params(run_records, 'distance_m', 'position_lat', 400, 5)
    long_weights = estimate_fourier_params(run_records, 'distance_m', 'position_long', 400, 5)

    x_vals = []
    y_vals = []

    for h in run_records:
        if h['distance_m'] and h['position_long']:
            x_vals.append(h['distance_m'])
            y_vals.append(h['position_long']) 

    x_array = np.array(x_vals)
    y_array = np.array(y_vals)

    lat_predicted = fourier_wave(x_array, 400, lat_weights)
    long_predicted = fourier_wave(x_array, 400, long_weights)

    plt.plot(x_vals, long_predicted, color='tab:blue')
    plt.plot(x_vals, y_array, color='tab:red')
    plt.show()


    for second in run_records:
        
        avg_sampling_rate = (end_time - start_time) / len(run_records)

        if second['speed_mps'] is not None:
            derived_distance += second['speed_mps']
            blended_distance = derived_distance
        
        if prev_second is not None and prev_second['position_lat'] is not None and prev_second['position_long'] is not None:
            lat1 = prev_second['position_lat']
            long1 = prev_second['position_long']
            lat2 = second['position_lat']
            long2 = second['position_long']
            gps_change = find_gps_bearing(lat1, long1, lat2, long2)
            if prev_change != 0:
                gps_diff =  find_angle_diff(prev_change, gps_change)
                state, momentum, blend_weight = state_machine(gps_diff, state, momentum, blend_weight)
                if gps_diff > bearing_anomaly_threshold and blend_weight < 0.6:
                    bearing_anomalies += 1
            prev_change = gps_change
            blended_distance = (second['distance_m'] * (1 - blend_weight) + derived_distance * blend_weight)

            timestamp = second['timestamp_unix']
            prev_timestamp = prev_second['timestamp_unix']

            #confidence score code

            #print('gps distance', second['distance_m'])
            #print('blended_distance', blended_distance)

            if timestamp is not None and prev_timestamp is not None:
                if abs((timestamp - prev_timestamp) -1) > 0.5:
                    timestamp_gaps += 1

                if blended_distance is not None and prev_blended is not None:
                    distance_change = blended_distance - prev_blended
                    if (timestamp - start_time) > 3 and (end_time - timestamp) > 3:
                        if len(rolling_distance) > 2 and abs(distance_change - distance_avg) > 18:
                            print('3', distance_change, distance_avg)
                            distance_change = distance_avg
                            distance_spikes += 7
                        elif len(rolling_distance) > 2 and abs(distance_change - distance_avg) > 10:
                            print('2', distance_change, distance_avg)
                            distance_change = distance_avg
                            distance_spikes += 3
                            print(blended_distance)
                        elif len(rolling_distance) > 2 and abs(distance_change - distance_avg) > 5:
                            print('1', distance_change, distance_avg)
                            distance_spikes += 1
                            print(blended_distance)
                    rolling_distance.append(distance_change)
                    distance_avg = sum(rolling_distance) / len(rolling_distance)
                    
                    lap_record_count += 1


        if prev_blended is not None and blended_distance < prev_blended:
            blended_distance = prev_blended

        if mode == 'track':
            lat_predicted = fourier_wave(second['distance_m'], 400, lat_weights)
            lat_residual = lat_predicted - second['position_lat']
            long_predicted = fourier_wave(second['distance_m'], 400, long_weights)
            long_residual = long_predicted - second['position_long']
            lat_residuals.append(lat_residual)
            long_residuals.append(long_residual)

        confidence_metrics = (timestamp_gaps, distance_spikes, bearing_anomalies, record_inconsistency)
        if any(x != 0 for x in confidence_metrics):
            confidence_score = find_confidence_score(timestamp_gaps, distance_spikes, bearing_anomalies, record_inconsistency)
            confidence_scores.append(confidence_score)

        #main lap logic
        
        if prev_blended is not None:
        
            if prev_blended < next_lap <= blended_distance:

                if blended_distance != prev_blended:
                    #interpolation + recording split time
                    progress = (next_lap - prev_blended) / (blended_distance - prev_blended)
                    prev_time = prev_second['timestamp_unix'] - start_time
                    current_time = second['timestamp_unix'] - start_time
                    lap_time = prev_time + progress * (current_time - prev_time)
                    lap_split = lap_time - last_lap_time
                    lap_splits.append(round(lap_split, 2))
                    last_lap_time = lap_time
                    lap_distances.append(next_lap)
                    next_lap += lap_distance
                    #remainder penalty calculating
                    expected_record = int(lap_split / avg_sampling_rate)
                    record_difference = abs(expected_record - lap_record_count)
                    if record_difference > 1:
                        record_inconsistency += record_difference
                    remainder_difference = abs(blended_distance - derived_distance)
                    if remainder_difference > 25:
                        remainder_penalty += 9
                    elif remainder_difference > 15:
                        remainder_penalty += 5
                    elif remainder_penalty > 8:
                        remainder_penalty += 2
                    #calculating rsme
                    if len(lat_residuals) > 0:
                        lat_rsme = np.sqrt(np.mean(np.array(lat_residuals)**2))
                    else:
                        lat_rsme = 0
                    if len(long_residuals) > 0:
                        long_rsme = np.sqrt(np.mean(np.array(long_residuals)**2))
                    else:
                        long_rsme = 0
                    #calculating and storing confidence scores
                    if lap_count > 0:
                        prev_confidence = lap_confidence_scores[lap_count - 1]
                        carryover_factor = min(0.2, lap_distance / 400 * 0.2)
                        carryover = max(0, min(10, max(0, 100 - prev_confidence) * carryover_factor))
                    else:
                        carryover = 0
                    avg_confidence = ((sum(confidence_scores) / len(confidence_scores) if confidence_scores else 100)
                                        - remainder_penalty * 3)
                    avg_confidence -= carryover
                    lap_confidence_scores.append(round(avg_confidence, 2))
                    score_factors = {'tmestamp_gaps': timestamp_gaps, 'distance_spikes': distance_spikes,
                       'bearing_anomolies': bearing_anomalies,'record_inconsistency': record_inconsistency,
                       'remainder_penalty': remainder_penalty, 'lat_rsme': lat_rsme, 'long_rsme': long_rsme}
                    print(f'lap {lap_count}')
                    print(f'score factors: {score_factors}')
                    print(f'lap confidence {avg_confidence}')
                    print(f'gps distance {second['distance_m']}')
                    print(f'Derived Distance {derived_distance}')
                    print(f'blended distance: {blended_distance}')
                    print(score_factors)
                    timestamp_gaps = 0
                    distance_spikes = 0
                    bearing_anomalies = 0
                    confidence_scores = []
                    record_inconsistency = 0
                    lap_record_count = 0
                    remainder_penalty = 0
                    lap_count += 1
                    lat_residuals = []
                    long_residuals = []
                    lat_rsme = 0
                    long_rsme = 0
                    continue

        prev_second = second
        prev_blended = blended_distance

    if blended_distance > (next_lap - lap_distance):
        distance_remainder = blended_distance - (next_lap - lap_distance)
        distance_remainder = round(distance_remainder, 2)
        time_remainder = ((end_time - start_time) - last_lap_time)
        time_remainder = round(time_remainder, 2)
    avg_total_confidence = round(sum(lap_confidence_scores) / len(lap_confidence_scores) if lap_confidence_scores else 100, 2)
    print(f'Distance Splits: {lap_splits}')
    print(f'gps distance {second['distance_m']}')
    print(f'Derived Distance {derived_distance}')
    print(f'blended distance: {blended_distance}')
    print(second['position_lat'], second['position_long'])
    print(f'Lap Confidence: {lap_confidence_scores} Total Confidence: {avg_total_confidence} ')
    print(f'remainder_penalty: {remainder_penalty}')

    
    dlap_data = lap_splits

    dlap_info = {
            'dlap_data': dlap_data,
            'distance_remainder': distance_remainder,
            'time_remainder': time_remainder,
            'lap_distances': lap_distances,
            'lap_confidence_scores': lap_confidence_scores,
            'avg_confidence': avg_total_confidence
        }
            

    return dlap_info


def time_lap_calculator(run_records, lap_time):
    start_time = run_records[0]['timestamp_unix']
    end_time = run_records[-1]['timestamp_unix']
    lap_distances = []
    lap_times = []
    next_lap = lap_time
    prev_lap = 0
    last_lap_time = None
    remainder_time = None
    remainder_distance = 0
    last_lap_time = 0
    prev_second = None
    derived_distance = 0
    prev_change = 0
    state = 'straight'
    blend_weight = 0
    momentum = 0
    blended_distance = 0
    prev_blended = None

    #confidence score stuff
    confidence_scores = []
    lap_confidence_scores = []
    confidence_score = 0
    timestamp_gaps = 0
    distance_spikes = 0
    rolling_distance = deque(maxlen=int(round(max(5, lap_time * 0.02))))
    distance_avg = 0
    bearing_anomaly_threshold = 0.55
    bearing_anomalies = 0
    lap_record_count = 0
    record_inconsistency = 0
    remainder_penalty = 0
    lap_count = 0
    avg_confidence = 100

    for second in run_records:
        avg_sampling_rate = (end_time - start_time) / len(run_records)
        distance = second['distance_m']
        if second['speed_mps'] is not None:
            derived_distance += second['speed_mps']
            blended_distance = derived_distance
        
        if distance is None:
            distance = derived_distance

        if prev_blended is None:
            prev_blended = blended_distance

        timestamp = second['timestamp_unix']
        prev_timestamp = prev_second['timestamp_unix'] if prev_second is not None else None
        speed = second['speed_mps']
        prev_speed = prev_second['speed_mps'] if prev_second is not None else None
        
        if prev_second is not None and prev_second['position_lat'] is not None and prev_second['position_long'] is not None:

            lat1 = prev_second['position_lat']
            long1 = prev_second['position_long']
            lat2 = second['position_lat']
            long2 = second['position_long']
            gps_change = find_gps_bearing(lat1, long1, lat2, long2)
            if prev_change != 0:
                gps_diff =  find_angle_diff(prev_change, gps_change)
                state, momentum, blend_weight = state_machine(gps_diff, state, momentum, blend_weight)
                if gps_diff > bearing_anomaly_threshold and blend_weight < 0.6:
                    bearing_anomalies += 1
            prev_change = gps_change
            blended_distance = (distance * (1 - blend_weight) + derived_distance * blend_weight)

        
        #confidence score code

        #print('gps distance', second['distance_m'])
        #print('blended_distance', blended_distance)

        if timestamp is not None and prev_second is not None:
            if abs((timestamp - prev_timestamp) -1) > 0.5:
                timestamp_gaps += 1

            if blended_distance is not None and prev_blended is not None:
                distance_change = blended_distance - prev_blended
                if (timestamp - start_time) > 3 and (end_time - timestamp) > 3:
                    if len(rolling_distance) > 2 and abs(distance_change - distance_avg) > 18:
                        print('3', distance_change, distance_avg)
                        distance_change = distance_avg
                        distance_spikes += 7
                    elif len(rolling_distance) > 2 and abs(distance_change - distance_avg) > 10:
                        print('2', distance_change, distance_avg)
                        distance_change = distance_avg
                        distance_spikes += 3
                        print(blended_distance)
                    elif len(rolling_distance) > 2 and abs(distance_change - distance_avg) > 5:
                        print('1', distance_change, distance_avg)
                        distance_spikes += 1
                        print(blended_distance)
                rolling_distance.append(distance_change)
                distance_avg = sum(rolling_distance) / len(rolling_distance)
                
                lap_record_count += 1

        if prev_blended is not None and blended_distance < prev_blended:
            blended_distance = prev_blended

        confidence_metrics = (timestamp_gaps, distance_spikes, bearing_anomalies, record_inconsistency, 
                                )
        if any(x != 0 for x in confidence_metrics):
            confidence_score = find_confidence_score(timestamp_gaps, distance_spikes, bearing_anomalies, record_inconsistency)
            confidence_scores.append(confidence_score)
            
        if prev_second is not None:
            current_time = second['timestamp_unix'] - start_time
            prev_time = prev_second['timestamp_unix'] - start_time

            if prev_time < next_lap <= current_time:
                progress = (next_lap - prev_time) / (current_time - prev_time)
                absolute_lap_distance = prev_blended + progress * (blended_distance - prev_blended)
                lap_distance = absolute_lap_distance - prev_lap
                lap_distances.append(round(lap_distance, 2))
                lap_times.append(round(next_lap, 2))
                next_lap += lap_time
                last_lap_time = current_time
                prev_lap = absolute_lap_distance 
                expected_record = int(lap_time / avg_sampling_rate)
                record_difference = abs(expected_record - lap_record_count)
                if record_difference > 1:
                    record_inconsistency += record_difference
                remainder_difference = abs(blended_distance - derived_distance)
                if remainder_difference > 25:
                    remainder_penalty += 9
                elif remainder_difference > 15:
                    remainder_penalty += 5
                elif remainder_penalty > 8:
                    remainder_penalty += 2
                if lap_count > 0:
                    prev_confidence = lap_confidence_scores[lap_count - 1]
                    carryover_factor = min(0.2, lap_distance / 400 * 0.2)
                    carryover = max(0, min(10, max(0, 100 - prev_confidence) * carryover_factor))
                else:
                    carryover = 0
                avg_confidence = ((sum(confidence_scores) / len(confidence_scores) if confidence_scores else 100)
                                    - remainder_penalty * 3)
                avg_confidence -= carryover
                lap_confidence_scores.append(round(avg_confidence, 2))
                score_factors = {'tmestamp_gaps': timestamp_gaps, 'distance_spikes': distance_spikes,
                    'bearing_anomolies': bearing_anomalies,'record_inconsistency': record_inconsistency,
                    'remainder_penalty': remainder_penalty}
                print(f'gps distance {second['distance_m']}')
                print(f'Derived Distance {derived_distance}')
                print(f'blended distance: {blended_distance}')
                print(score_factors)
                timestamp_gaps = 0
                distance_spikes = 0
                bearing_anomalies = 0
                confidence_scores = []
                record_inconsistency = 0
                lap_record_count = 0
                remainder_penalty = 0
                lap_count += 1
                continue
        prev_second = second
        prev_blended = blended_distance

    total_elapsed = end_time - start_time
    if last_lap_time < total_elapsed:
        remainder_distance = round((blended_distance - prev_lap), 2)
        remainder_time = round((total_elapsed - last_lap_time), 2)

    avg_total_confidence = round(sum(lap_confidence_scores) / len(lap_confidence_scores) if lap_confidence_scores else 100, 2)

    print(f'''Lap Distances: {lap_distances} Distance Remainder: {remainder_distance}
            Lap Times: {lap_times}
            Time Remainder: {remainder_time}''')

    tlap_data = lap_distances
    tlap_info = {
                'tlap_data': tlap_data,
                'remainder_distance': remainder_distance,
                'lap_times': lap_times,
                'remainder_time': remainder_time,
                'lap_confidence_scores': lap_confidence_scores,
                'avg_confidence': avg_total_confidence
            }
    
    return tlap_info
