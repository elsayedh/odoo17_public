from odoo import fields, models, api, Command, _
from odoo.tools import groupby
import requests
from datetime import timedelta, datetime
import json
import logging

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _name = 'stock.picking'
    _inherit = ['stock.picking', 'stock.pw.mixin']

    _sql_constraints = [('pw_id_unique', 'unique(pw_id,)', 'pw_id already exist.')]

    def cron_fetch_online_orders(self, date=None, date_to=None):
        self.fetch_entries(
            order_type='online',
            date=date,
            date_to=date_to,
            json_payload=True,
            transaction_list_name='orderList',
            endpoint_param_key='pw_online_order'
        )
