# -*- coding: utf-8 -*-
# from odoo import http


# class PlPwIntegration(http.Controller):
#     @http.route('/pl_pw_integration/pl_pw_integration', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/pl_pw_integration/pl_pw_integration/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('pl_pw_integration.listing', {
#             'root': '/pl_pw_integration/pl_pw_integration',
#             'objects': http.request.env['pl_pw_integration.pl_pw_integration'].search([]),
#         })

#     @http.route('/pl_pw_integration/pl_pw_integration/objects/<model("pl_pw_integration.pl_pw_integration"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('pl_pw_integration.object', {
#             'object': obj
#         })

