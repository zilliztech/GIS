"""
Copyright (C) 2019-2020 Zilliz. All rights reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import json

from flask import Blueprint, jsonify, request

from arctern.util.vega import vega_choroplethmap, vega_heatmap, vega_pointmap
from arctern_pyspark import choroplethmap, heatmap, pointmap
from app.common import spark, token, utils
from app.nyctaxi import data as nyctaxi_data

API = Blueprint('nyctaxi_api', __name__)


@API.route('/dbs')
@token.AUTH.login_required
def dbs():
    """
    /dbs handler
    """
    content = []

    info = {}
    info['id'] = '1'
    info['name'] = 'nyc taxi'
    info['type'] = 'spark'

    content.append(info)

    return jsonify(status='success', code=200, data=content)


@API.route("/db/tables", methods=['POST'])
@token.AUTH.login_required
def db_tables():
    """
    /db/tables handler
    """
    if not utils.check_json(request.json, 'id'):
        return jsonify(status='error', code=-1, message='json error: id is not exist')
    content = nyctaxi_data.GLOBAL_TABLE_LIST
    return jsonify(status="success", code=200, data=content)


@API.route("/db/table/info", methods=['POST'])
@token.AUTH.login_required
def db_table_info():
    """
    /db/table/info handler
    """
    if not utils.check_json(request.json, 'id') \
            or not utils.check_json(request.json, 'table'):
        return jsonify(status='error', code=-1, message='query format error')

    content = []

    result = spark.Spark.run_for_json(
        "desc table {}".format(request.json['table']))

    for row in result:
        obj = json.loads(row)
        content.append(obj)

    return jsonify(status="success", code=200, data=content)


@API.route("/db/query", methods=['POST'])
@token.AUTH.login_required
def db_query():
    """
    /db/query handler
    """
    if not utils.check_json(request.json, 'id') \
            or not utils.check_json(request.json, 'query') \
            or not utils.check_json(request.json['query'], 'type') \
            or not utils.check_json(request.json['query'], 'sql'):
        return jsonify(status='error', code=-1, message='query format error')

    content = {}
    content['sql'] = request.json['query']['sql']
    content['err'] = False

    res = spark.Spark.run(request.json['query']['sql'])

    if request.json['query']['type'] == 'sql':
        data = []
        for row in res:
            obj = json.loads(row)
            data.append(obj)
        content['result'] = data
    else:
        if not utils.check_json(request.json['query'], 'params'):
            return jsonify(status='error', code=-1, message='query format error')
        query_params = request.json['query']['params']
        if request.json['query']['type'] == 'point':
            vega = vega_pointmap(
                int(query_params['width']),
                int(query_params['height']),
                query_params['point']['bounding_box'],
                int(query_params['point']['stroke_width']),
                query_params['point']['stroke'],
                float(query_params['point']['opacity']),
                query_params['point']['coordinate'])
            data = pointmap(res, vega)
            content['result'] = data
        elif request.json['query']['type'] == 'heat':
            vega = vega_heatmap(
                int(query_params['width']),
                int(query_params['height']),
                float(query_params['heat']['map_scale']),
                query_params['heat']['bounding_box'],
                query_params['heat']['coordinate'])
            data = heatmap(res, vega)
            content['result'] = data
        elif request.json['query']['type'] == 'choropleth':
            vega = vega_choroplethmap(
                int(query_params['width']),
                int(query_params['height']),
                query_params['choropleth']['bounding_box'],
                query_params['choropleth']['color_style'],
                query_params['choropleth']['rule'],
                float(query_params['choropleth']['opacity']),
                query_params['choropleth']['coordinate'])
            data = choroplethmap(res, vega)
            content['result'] = data
        else:
            return jsonify(status="error",
                           code=-1,
                           message='{} not support'.format(request.json['query']['type']))
    return jsonify(status="success", code=200, data=content)
