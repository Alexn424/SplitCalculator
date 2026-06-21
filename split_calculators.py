import math


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



def state_machine(angle_diff, state, momentum, blend_weight):
    current_state = state
    low_threshold = 0.03
    high_threshold = 0.1
    c_blend_weight = blend_weight
    c_blend_weight = max(0, min(1, c_blend_weight))
    cur_threshold = 3
    str_threshold = -5


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
                c_blend_weight = 0
        
        elif low_threshold < angle_diff < high_threshold:
            current_state = 'blended'
        
        elif high_threshold <= angle_diff:
            momentum += 1
            c_blend_weight += 0.33
            momentum = max(-5, min(3, momentum))
            if momentum == cur_threshold:
                current_state = 'curved'
                c_blend_weight = 1
        
    return current_state, momentum, c_blend_weight
        

def distance_lap_calculator(run_records, lap_distance):
    lap_splits = []
    start_time = run_records[0]['timestamp_unix']
    end_time = run_records[-1]['timestamp_unix']
    next_lap = lap_distance
    last_lap_time = start_time
    prev_second = None
    derived_distance = 0
    prev_change = 0
    state = 'straight'
    blend_weight = 0
    momentum = 0
    blended_distance = 0
    prev_blended = None

    for second in run_records:
        
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
            prev_change = gps_change
            blended_distance = (second['distance_m'] * (1 - blend_weight) + derived_distance * blend_weight)
        
        if prev_blended is not None:
            if blended_distance == next_lap:
                lap_splits.append(round(second['timestamp_unix'] - last_lap_time, 2))
                next_lap += lap_distance
                last_lap_time = second['timestamp_unix']
                continue
            elif blended_distance > next_lap:

                if blended_distance != prev_blended:
                    progress = (next_lap - prev_blended) / (blended_distance - prev_blended)
                    prev_time = prev_second['timestamp_unix']
                    current_time = second['timestamp_unix']
                    lap_time = prev_time + progress * (current_time - prev_time)
                    lap_split = lap_time - last_lap_time
                    lap_splits.append(round(lap_split, 2))
                    last_lap_time = lap_time
                    next_lap += lap_distance
                    continue

        prev_second = second
        prev_blended = blended_distance

    if last_lap_time < end_time:
        remainder = end_time - last_lap_time
        lap_splits.append(round(remainder, 2))
    distance = blended_distance
    print(f'Distance Splits: {lap_splits}')
    print(f'total distance: {distance}')

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
    print(lap_distances, remainder_time)
    return lap_distances, remainder_time
