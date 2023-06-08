#!/usr/bin/env python3
import dataclasses

from django.shortcuts import render
from django.http import JsonResponse
from elasticsearch import Elasticsearch
from . import data_processing
import json
import logging
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import configparser

# the chance of using ini:

# ini_path = r"chartsite.ini"
# config = configparser.ConfigParser()
# config.read(ini_path)
# last_date_config = configparser.ConfigParser()
# ip = config.get('ELASTIC', 'ip')
# port = config.get('ELASTIC', 'port')
# login = config.get('ELASTIC', 'login')
# password = config.get('ELASTIC', 'password')

import os
from dotenv import load_dotenv

load_dotenv()

ip = os.environ.get('ELASTIC_IP')
port = os.environ.get('ELASTIC_PORT')
login = os.environ.get('ELASTIC_LOGIN')
password = os.environ.get('ELASTIC_PASSWORD')

logger = logging.getLogger("mylogger")


@dataclasses.dataclass
class Chart:
    # default start_time is last 10 minutes
    START_TIME = str(datetime.now() - timedelta(minutes=10))
    END_TIME = str(datetime.now())

    DATA = {}
    _es = ''


def elastic():
    """getting information straight from elasticsearch without sorting or altering it"""
    Chart._es = Elasticsearch([f"http://{ip}:{port}"], http_auth=(str(login), str(password)))
    return data_processing.Data.get_testing_sessions(Chart._es, Chart.START_TIME, Chart.END_TIME)


def get_data(testings_set):
    """sorting raw elasticsearch data and writing the result into global DATA"""
    data = []
    for testing_session in testings_set:
        info = data_processing.Data.get_testing_session_info(Chart._es, testing_session)
        processed_data = data_processing.Data.process_info_from_testing_session(info)
        data.append(processed_data)

    for row in data:
        id = row.get('user_id')
        if id is None:
            continue
        session = row.get('testing_session_uuid')

        if Chart.DATA.get(id) is not None:
            device = {'device': row.get('device'),
                      'device_family': row.get('device_family'),
                      'message': row.get('message'),
                      'time_points': row.get('@timestamp')}
            Chart.DATA[id][session] = device
        else:
            Chart.DATA[id] = {session: {'device': row.get('device'),
                                        'device_family': row.get('device_family'),
                                        'message': row.get('message'),
                                        'time_points': row.get('@timestamp')}}

    sort = dict(sorted(Chart.DATA.items()))
    Chart.DATA = sort


def filtered_data(basic=None):
    """changing existing data into chart format"""
    families = {'Total': 0}
    yLabels = {}
    if basic is None:
        raw_data = elastic()
        get_data(raw_data)
        basic = Chart.DATA
    sets = {}
    test_y_count = 0
    for op_id in basic:
        for session in basic[op_id]:
            test_y_count += 1
            label = session
            try:
                families['Total'] += 1
                families[basic[op_id][session].get('device_family')] += 1
            except KeyError:
                families[basic[op_id][session].get('device_family')] = 1
            for point in basic[op_id][session].get('time_points'):
                data = {'t': point, 'y': test_y_count}
                yLabels[test_y_count] = {'user_id': op_id,
                                         'device': basic[op_id][session].get('device'),
                                         'device_family': basic[op_id][session].get('device_family'),
                                         'message': basic[op_id][session].get('message')}
                try:
                    sets[label].append(data)
                except KeyError:
                    sets[label] = [data]
    datasets = []
    for key in sets:
        datasets.append({'label': key, 'data': sets[key], 'borderColor': "#006174", 'fill': False, })
    result = {
        'type': 'line',
        'data': {
            'datasets': datasets,
        },
        'options': {
            'animation': {
                'onComplete': '',
                'duration': 0
            },
            'hover': {
                'mode': None,
                'animationDuration': 0
            },
            'tooltips': {
                'callbacks': {
                    'label': '',
                    'title': ''
                }
            },
            'scales': {
                'xAxes': [{
                    'type': 'time',
                    'distribution': "linear",
                    'ticks': {
                        'min': Chart.START_TIME,
                        'max': Chart.END_TIME,
                    },
                    'time': {
                        'displayFormats': {
                            'millisecond': 'HH:mm:ss.SSS',
                            'second': 'HH:mm:ss',
                            'minute': 'HH:mm',
                            'hour': 'DD.MM HH',
                            'day': 'DD/MM/YYYY',
                            'week': 'DD/MM/YYYY',
                            'month': 'DD/MM/YYYY',
                            'quarter': 'DD/MM/YYYY',
                            'year': 'DD/MM/YYYY',
                        }
                    },
                },
                ],
                'yAxes': [{
                    'gridLines': {
                        'color': 'black',
                        'drawTicks': True
                    },
                    'ticks': {
                        'fontSize': 10,
                        'callback': '',
                        'autoSkip': False,
                        'maxRotation': 90,
                        'minRotation': 30,
                        'beginAtZero': True,
                        'stepSize': 1,
                    },
                }]
            },
            'responsive': True,
            'legend': {
                'display': False,
            },
        }
    }
    fam_res = []
    for family in families:
        fam_res.append(f'{family}: {families[family]} ')

    return result, fam_res, yLabels


def time_update(request):
    if request.POST.get('new_time') is not None:
        new_time = str(request.POST.get('new_time'))
        if new_time == "day":
            start = datetime.now() - timedelta(hours=24)
        elif new_time == "month":
            start = datetime.now() - relativedelta(months=1)
        elif new_time == "week":
            start = datetime.now() - timedelta(days=7)
        elif new_time == "1h":
            start = datetime.now() - timedelta(hours=1)
        elif new_time == "2h":
            start = datetime.now() - timedelta(hours=2)
        elif new_time == "10min":
            start = datetime.now() - timedelta(minutes=10)
        else:
            start = new_time
        Chart.START_TIME = str(start)
        return JsonResponse({'response': f'from {Chart.START_TIME} to {Chart.END_TIME}'})
    elif request.POST.get('calen_time') is not None:
        time = str(request.POST.get('calen_time'))
        try:
            current_date = datetime.strptime(Chart.START_TIME, '%Y-%m-%d %H:%M:%S.%f').date()
        except ValueError:
            current_date = datetime.strptime(Chart.START_TIME, '%Y-%m-%d %H:%M:%S').date()
        Chart.START_TIME = f'{current_date} {time}:00.000000'
        return JsonResponse({'response': f'from {Chart.START_TIME} to {Chart.END_TIME}'})


def auto_update(request):
    Chart.DATA = {}
    Chart.END_TIME = str(datetime.now())
    try:
        new_start = datetime.strptime(Chart.START_TIME, '%Y-%m-%d %H:%M:%S.%f') + timedelta(milliseconds=30000)
    except ValueError:
        try:
            new_start = datetime.strptime(Chart.START_TIME, '%Y-%m-%d %H:%M:%S') + timedelta(milliseconds=30000)
        except ValueError:
            new_start = datetime.strptime(Chart.START_TIME, '%Y-%m-%d') + timedelta(milliseconds=30000)
    Chart.START_TIME = str(new_start)

    info, families, yLabels = filtered_data()
    return JsonResponse({'info': info, 'families': families, 'yLabels': yLabels})


def chart(request):
    Chart.DATA = {}
    info, families, yLabels = filtered_data()
    return render(request, 'line_chart.html',
                  {'info': json.dumps(info), 'families': families, 'yLabels': json.dumps(yLabels)})
