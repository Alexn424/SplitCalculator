from app import time_lap_calculator, distance_lap_calculator
from fitparse import FitFile


path = r'uploads/Garmin Runs 5-24-26/2026-04-15-18-22-53.fit'
#fit_file = FitFile(path)
#records = list(fit_file.get_messages('record'))
#print({f.name: f.value for f in records[30]})

#try adding per second switches with change in lat/long be a conditional

def find_mile_pace(time, distance):
    mile = 1609.344
    multiplier = mile / distance
    return time * multiplier

def find_mile_paces(lap_splits, lap_distance):
    mile_paces = []
    for j in lap_splits:
        mile_pace = find_mile_pace(j, lap_distance)
        minute = int(mile_pace // 60)
        seconds = int(round(mile_pace % 60))
        if seconds == 60:
            minute += 1
            seconds = 0
        mile_paces.append(f'{minute}:{seconds:02d}')
    return mile_paces

def find_clean_splits(lap_splits):
    clean_splits = []
    for i in lap_splits:
        if i > 60:
            digit = int(i / 60)
            seconds = round(i - (60 * digit), 2)
            clean_splits.append(f'{digit}:{seconds:05.2f}')
        else:
            clean_splits.append(i)
    cumulative_time = sum(lap_splits)
    minute = int(cumulative_time // 60)
    seconds = round(cumulative_time % 60, 2)
    if seconds == 60:
        minute += 1
        seconds = 0
    return clean_splits, f'{minute}:{seconds:05.2f}'

def find_time_mile_paces(time_splits, lap_time, remainder_time=None):
    mile_paces = []
    for idx, i in enumerate(time_splits):
        is_last = idx == len(time_splits) - 1
        window_time = remainder_time if (is_last and remainder_time) else lap_time
        meterps = i / window_time
        secondpm = 1609.34 / meterps
        minute = int(secondpm // 60)
        seconds = int(round(secondpm % 60))
        if seconds == 60:
            minute += 1
            seconds = 0
        mile_paces.append(f'{minute}:{seconds:02d}')
    return mile_paces

run_id = 110
lap_distance = 400
lap_splits = distance_lap_calculator(run_id, lap_distance)
dclean_splits, dcumulative = find_clean_splits(lap_splits)
dmile_paces = find_mile_paces(lap_splits, lap_distance)
print(f'{dclean_splits}\n{dmile_paces}\n{dcumulative}')

lap_time = 150
time_splits, remainder_time = time_lap_calculator(run_id, lap_time)
tmile_paces = find_time_mile_paces(time_splits, lap_time, remainder_time)
cumulative_distance = round(sum(time_splits), 2)
print(f'{time_splits}\n{tmile_paces}\n{cumulative_distance}m')