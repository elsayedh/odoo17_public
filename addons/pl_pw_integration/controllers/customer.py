import json

from odoo import http
from odoo.http import request
from odoo import _
from datetime import datetime


class Customer(http.Controller):

    def _action_log(self, desc, log_type, pw_order_id=False, order_id=False):
        request.env['pw.log'].sudo().create({
            'date': datetime.now(),
            'name': desc,
            'sale_id': False,
            'pw_id': pw_order_id,
            'log_type': log_type
        })

    def get_token(self, req):
        token = None
        environ = req.httprequest.environ
        HTTP_AUTHORIZATION = environ.get('HTTP_AUTHORIZATION')
        if HTTP_AUTHORIZATION:
            res = HTTP_AUTHORIZATION.split(' ')
            if len(res) > 1:
                token = res[1]
        return token

    def token_auth(self, token=None):
        if not token:
            token = self.get_token(http.request)
        _id = None
        if token:
            ir_config = request.env['ir.config_parameter'].sudo()
            odoo_api_token = ir_config.get_param('pl_pw_integration.odoo_api_token')
            if odoo_api_token == token:
                self._action_log('Authentication successful', log_type='info')
                return True
            else:
                self._action_log('Authentication Failed', log_type='error')
                return False

    def unauthorized_msg(self):
        return {
            "status_code": 403,
            "errors": [{
                "code": 403,
                "msg": _("Not Authorized!")
            }]
        }

    @http.route('/customer/register', auth="public", method=['POST'], website=False, csrf=False, cors="*")
    def create_and_update_customer(self, ):
        values = {}
        authorized = self.token_auth()
        if not authorized:
            return self.unauthorized_msg()
        body = request.get_json_data()
        if not body or not body[0] or not 'POS_info' in body[0]:
            self._action_log('Data Not Provided In Request', log_type='error')
            return json.dumps({"status_code": 401,
                               "errors": {'code': 1001, 'msg': "Data Not Provided In Request."}})
        result = {}
        for item in body:
            params_items = item['POS_info']
            if not params_items:
                self._action_log('POS_info Not In Body', log_type='error')
                return json.dumps({"status_code": 401,
                                   "errors": {'code': 1004,
                                              'msg': "POS_info Not In Body."}})
            for params in params_items:
                if 'POS_ID' not in params:
                    self._action_log('POS_ID Not Provided In Request Data', log_type='error')
                    json.dumps({"status_code": 401,
                                "errors": {'code': 1001, 'msg': "Please Provide POS_ID."}})
                if 'Name_AR' not in params:
                    self._action_log('Name Of Customer Not Provided In Request Data', log_type='error')
                    return json.dumps({"status_code": 401,
                                       "errors": {'code': 1002,
                                                  'msg': "Name Of Customer Not Provided In Request Data."}})
                partner_id = request.env['res.partner'].sudo().search([('pw_pos_id', '=', params['POS_ID'])])
                data = {'name': params['Name_AR']}
                try:
                    if 'City' in params:
                        data['city'] = params['City']
                    if 'Rep_ID' in params:
                        Rep_ID = params['Rep_ID']
                        user_id = request.env['res.users'].sudo().search([('pw_id', '=', Rep_ID)])
                        if user_id:
                            data['user_id'] = user_id[0].id
                        else:
                            self._action_log('New User Create For %s' % Rep_ID, log_type='warning')
                            data['user_id'] = request.env['res.users'].sudo().create(
                                {'login': Rep_ID, 'name': Rep_ID, 'pw_id': Rep_ID}).id
                    if partner_id:
                        partner_id.sudo().write(data)
                        msg = 'update customer %s successfully finished' % (params['POS_ID'])
                        self._action_log(msg, log_type='info')
                        result.update({params['POS_ID']: {"status_code": 200, "status": "Customer Updated", }})
                        continue
                    else:
                        data['pw_pos_id'] = params['POS_ID']
                        partner_id = request.env['res.partner'].sudo().create(data)
                        msg = 'create customer %s successfully finished' % (params['POS_ID'])
                        self._action_log(msg, log_type='info')
                        result.update({params['POS_ID']: {"status_code": 200, "status": "Customer Created", }})
                        continue
                except Exception as e:
                    msg = 'Error while try create or update contact %s ,%s' % (params['POS_ID'], e)
                    self._action_log(msg, log_type='error')
                    return json.dumps({'status_code': 401, "errors": {'code': 1003, 'msg': msg}})
        return json.dumps(result)
