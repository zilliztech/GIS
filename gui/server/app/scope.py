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

import uuid
import json

from flask import Blueprint, jsonify, request, redirect, url_for

from app.common import utils, log
from app.codegen import *

API = Blueprint("scope_api", __name__)

# TODO:
# if zeppelin is required later, we need a map between scope of server and notebook of zeppelin.
# Maybe the map should be persistent in sqlite or any other database.
_SCOPE = {}

@API.route('/scope', methods=['POST'])
def create_scope():
    log.INSTANCE.info("POST /scope: {}".format(request.json))
    
    scope = request.json.get("scope")
    if scope in _SCOPE:
        return jsonify(status="error", code=-1, message="sorry, scope_id exists!")
    if scope is None:
        scope = str(uuid.uuid1()).replace("-", "")
    _SCOPE[scope] = dict()
    # create default SparkSession in scope
    session_code = _generate_session_code("spark")
    exec(session_code, _SCOPE[scope])
    return jsonify(status="success", code=200, message="create scope successfully!", scope=scope)

@API.route('/scope/<scope_name>', methods=['DELETE'])
def remove_scope(scope_name):
    log.INSTANCE.info("DELETE /scope/{}".format(scope_name))

    if scope_name not in _SCOPE:
        return jsonify(status="error", code=-1, message="scope {} not found!".format(scope_name))
    del _SCOPE[scope_name]
    return jsonify(status="success", code=200, message="remove scope {} successfully!".format(scope_name))

@API.route('/command', methods=['POST'])
def execute_command():
    log.INSTANCE.info("POST /command: {}".format(request.json))

    scope = request.json.get("scope")
    code = request.json.get("command")
    if scope not in _SCOPE:
        return jsonify(status="error", code=-1, message="scope {} not found!".format(scope))
    if code is None:
        return jsonify(status="success", code=200, message="execute command successfully!")
    print("scope", scope)
    print(code)
    exec(code, _SCOPE[scope])
    return jsonify(status="success", code=200, message="execute command successfully!")

@API.route('/loadfile', methods=['POST'])
def load_file():
    log.INSTANCE.info("POST /loadfile: {}".format(request.json))

    scope = request.json.get('scope')
    if scope not in _SCOPE:
        return jsonify(status='error', code=-1, message='scope {} not found!'.format(scope))

    session = request.json.get('session')
    if session is None:
        session = 'spark'
    
    tables = request.json.get('tables')
    for table in tables:
        load_code = _generate_load_code(table, session)
        print(load_code)
        exec(load_code, _SCOPE[scope])
    return jsonify(status='success', code=200, message='load table successfully!')

@API.route('/savetable', methods=['POST'])
def save_table():
    log.INSTANCE.info("POST /savetable: {}".format(request.json))

    scope = request.json.get('scope')
    if scope not in _SCOPE:
        return jsonify(status='error', code=-1, message='scope {} not found!'.format(scope))

    session = request.json.get('session')
    if session is None:
        session = 'spark'

    tables = request.json.get('tables')
    for table in tables:
        save_code = _generate_save_code(table, session)
        print(save_code)
        exec(save_code, _SCOPE[scope])
    return jsonify(status='success', code=200, message='save table successfully!')

@API.route('/table', methods=['GET'])
def table_info():
    log.INSTANCE.info("GET /table: {}".format(request.args))

    scope = request.args.get('scope')
    if scope not in _SCOPE:
        return jsonify(status='error', code=-1, message='scope {} not found!'.format(scope))

    session = request.args.get('session')
    if session is None:
        session = 'spark'

    table_name = request.args.get('table')
    # use eval to get result instead of exec
    table_schema_code = _generate_table_schema_code(table_name, session)
    json_schema = eval(table_schema_code, _SCOPE[scope])
    schema = [json.loads(row) for row in json_schema]

    table_count_code = _generate_table_count_code(table_name, session)
    json_count = eval(table_count_code, _SCOPE[scope])
    num_rows = json.loads(json_count[0])

    return jsonify(
        status="success",
        code=200,
        table=table_name,
        schema=schema,
        **num_rows,
    )

@API.route('/query', methods=['POST'])
def query():
    log.INSTANCE.info("POST /query: {}".format(request.json))

    scope = request.json.get('scope')
    if scope not in _SCOPE:
        return jsonify(status='error', code=-1, message='scope {} not found!'.format(scope))

    session = request.json.get('session')
    if session is None:
        session = 'spark'

    sql = request.json.get('sql')

    collect_result = request.json.get('collect_result')
    if collect_result is None or collect_result == '1':
        code = _generate_run_for_json_code(sql, session)
        json_res = eval(code, _SCOPE[scope])
        return jsonify(
            status='success',
            code=200,
            result=[json.loads(row) for row in json_res],
            message="execute sql successfully!",
        )
    
    # just run sql
    code = _generate_run_sql_code(sql, session)
    exec(code, _SCOPE[scope])
    return jsonify(
        status='success',
        code=200,
        message="execute sql successfully!",
    )

def render(payload, render_type):
    generate_func = {
        "pointmap": _generate_pointmap_code,
        "heatmap": _generate_heatmap_code,
        "choroplethmap": _generate_choropleth_map_code,
        "weighted_pointmap": _generate_weighted_map_code,
    }

    log.INSTANCE.info("POST /{}: {}".format(render_type, payload))

    scope = payload.get('scope')
    if scope not in _SCOPE:
        return jsonify(status='error', code=-1, message='scope {} not found!'.format(scope))

    session = payload.get('session')
    if session is None:
        session = 'spark'

    sql = payload.get('sql')
    params = payload.get('params')

    sql_code, vega_code = generate_func[render_type](sql, params, session_name)

    res = eval(sql_code, _SCOPE[scope])
    vega = eval(vega_code, _SCOPE[scope])
    # try to avoid the conflict of variable in scope
    uid = str(uuid.uuid1()).replace('-', '')
    vega_var = 'vega_' + uid
    res_var = 'res_' + uid
    args = {
        vega_var: vega,
        res_var: res
    }
    data = eval('{}({}, {})'.format(render_type, vega_var, res_var), _SCOPE[scope], args)
    return "success", 200, data

@API.route('/pointmap', methods=['POST'])
def pointmap():
    status, code, result = render(request.json, 'pointmap')
    return jsonify(
        status=status,
        code=code,
        result=result,
    )

@API.route('/heatmap', methods=['POST'])
def heatmap():
    status, code, result = render(request.json, 'heatmap')
    return jsonify(
        status=status,
        code=code,
        result=result,
    )

@API.route('/choroplethmap', methods=['POST'])
def choroplethmap():
    status, code, result = render(request.json, 'choroplethmap')
    return jsonify(
        status=status,
        code=code,
        result=result,
    )

@API.route('/weighted_pointmap', methods=['POST'])
def weighted_pointmap():
    status, code, result = render(request.json, 'weighted_pointmap')
    return jsonify(
        status=status,
        code=code,
        result=result,
    )

