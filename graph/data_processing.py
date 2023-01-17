#! /usr/bin/env python
from datetime import datetime


class Data:
    @staticmethod
    def _get_date_formats():
        date_formats = [
            '%d.%m.%Y %H:%M', '%d.%m.%Y', '%d.%m.%Y %H:%M:%S', '%Y-%m-%d %H',
            '%Y-%m-%d''T''%H:%M:%S.%f', '%Y-%m-%d''T''%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d',
            '%Y-%m-%d %H:%M:%S.%f',
        ]
        return date_formats

    @staticmethod
    def get_date_standart_format(date) -> str:
        """
        Returns data in "%Y-%m-%dT%H:%M:%S.%f" format
        """

        date_formats = Data._get_date_formats()

        if isinstance(date, str):
            date = Data.get_datetime(date)

        for _format in date_formats:
            try:
                datetime_date = date
                return datetime_date.strftime("%Y-%m-%dT%H:%M:%S.%f")
            except AttributeError:
                raise AttributeError("Wrong type, datetime expected")
        raise ValueError("Unsupported date format")

    @staticmethod
    def get_datetime(date) -> datetime:
        """
        Returns datetime object
        """
        date_formats = Data._get_date_formats()

        for _format in date_formats:
            try:
                datetime_date = datetime.strptime(date, _format)
                return datetime_date
            except ValueError:
                continue
        else:
            raise ValueError("Unsupported date format")

    @staticmethod
    def process_info_from_testing_session(info):
        device = info[0]["device"]
        user_id = info[0]["user_id"]
        message = info[0]["message"]
        testing_session_uuid = info[0]["testing_session_uuid"]
        device_family = info[0]["device_family"]
        _timestamp = []
        for _dict in info:
            _timestamp.append(_dict['@timestamp'])

        return {
            "device": device,
            "testing_session_uuid": testing_session_uuid,
            "@timestamp": _timestamp,
            "device_family": device_family,
            "message": message,
            "user_id": user_id
        }

    @staticmethod
    def get_testing_session_info(es, testing_session_uuid, index="*devices-2*", size=10000, to_print=False) -> list:
        """
        Возвращает отсортированный список с полями _source по данному testing_session_uuid
        """

        query = {
            "bool": {
                "must": {
                    "match": {
                        "testing_session_uuid.keyword": testing_session_uuid
                    }
                }
            }
        }

        _res = es.search(index=index, query=query, size=size)
        results = [_res["hits"]["hits"][x]["_source"] for x in range(len(_res["hits"]["hits"]))]
        whole_results = [] + results

        size_search = len(_res["hits"]["hits"])
        if size_search == size:
            tiebreak = _res["hits"]["hits"][-1]["sort"]
        count = 0
        while size_search == size:
            count += 1
            _res_new = es.search(index=index, query=query, size=size, search_after=tiebreak)
            tiebreak = _res_new["hits"]["hits"][-1]["sort"]
            size_search = len(_res_new["hits"]["hits"])
            results = [_res_new["hits"]["hits"][x]["_source"] for x in range(len(_res_new["hits"]["hits"]))]
            whole_results += results

        for _ in range(len(whole_results)):
            whole_results[_]["@timestamp_sort"] = Data.get_datetime(whole_results[_]["@timestamp"])

        whole_results = sorted(whole_results, key=lambda x: x["@timestamp_sort"], reverse=True)
        return whole_results

    @staticmethod
    def get_testing_sessions(es, start_time, end_time):
        """
            Возвращает все testing_session_uuid в выбраном временом промежутке
        """
        date_start = Data.get_date_standart_format(start_time)
        date_end = Data.get_date_standart_format(end_time)
        query = {
            "bool": {
                "must": [
                    {
                        "range": {
                            "@timestamp": {
                                "gte": date_start,
                                "lt": date_end
                            }
                        }
                    }
                ]
            }
        }
        aggregations = {
            "testing_sessions": {
                "composite": {
                    "size": 10000,
                    "sources": [
                        {
                            "testing_sessions": {
                                "terms": {
                                    "field": "testing_session_uuid.keyword"
                                }
                            }
                        }
                    ]
                }
            }
        }

        testings_set = set()

        _testing_sessions = es.search(index="*devices-2*", size=10000, query=query, aggregations=aggregations)

        search_after = _testing_sessions["aggregations"]["testing_sessions"].get("after_key")
        scroll_size = len(_testing_sessions["hits"]["hits"])

        _testing_sessions = _testing_sessions["aggregations"]["testing_sessions"]["buckets"]
        _testing_sessions = [x["key"]["testing_sessions"] for x in _testing_sessions]
        testings_set.update(_testing_sessions)
        if not search_after:
            return _testing_sessions

        results = [_testing_sessions]
        while scroll_size > 0:
            aggregations["testing_sessions"]["composite"]["after"] = search_after
            _testing_sessions = es.search(index="*devices-2*", query=query, size=10000,
                                          aggregations=aggregations)
            search_after = _testing_sessions["aggregations"]["testing_sessions"].get("after_key")
            if not search_after:
                break
            scroll_size = len(_testing_sessions["hits"]["hits"])
            _testing_sessions = _testing_sessions["aggregations"]["testing_sessions"]["buckets"]
            _testing_sessions = [x["key"]["testing_sessions"] for x in _testing_sessions]
            results.append(_testing_sessions)
            testings_set.update(_testing_sessions)
        return testings_set
