from odoo import fields, models, api, _, Command
import requests
from datetime import timedelta
import json
from collections import defaultdict

import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _name = 'account.move'
    _inherit = ['account.move', 'account.pw.mixin']

    _sql_constraints = [('pw_id_unique', 'unique(pw_id,)', 'pw_id already exist.')]

    def action_cancel_duplicated_entries(self):
        for order in self:
            if order.state != 'cancel':
                ids = self.ids
                ids.remove(order.id)
                other_invoice_ids = self.env['account.move'].search(
                    [('id', 'in', ids), ('state', '!=', 'cancel'), ('pw_id', '=', order.pw_id)])

                for other_invoice in other_invoice_ids:
                    other_invoice.button_draft()
                    other_invoice.button_cancel()

    @api.model
    def cron_fetch_pw_balanced_transfer_entries(self, date=None, date_to=None):
        self.fetch_entries(
            transaction_type='Balanced transfer',
            date=date,
            date_to=date_to,
            json_payload=True,
            transaction_list_name='TransactionList',
            trans_id_key='OrderID',
            amount_key='Amount',
            description_key='Description',
            use_subtype=True,
            sender_id_key='Sender ID',
            receiver_id_key='Receiver ID',
            endpoint_param_key='pw_transaction_by_date_endpoint',
        )

    @api.model
    def cron_fetch_pw_balance_pulled_entries(self, date=None, date_to=None):
        self.fetch_entries(
            transaction_type='balance pulled',
            date=date,
            date_to=date_to,
            json_payload=True,
            transaction_list_name='TransactionList',
            trans_id_key='OrderID',
            amount_key='Amount',
            description_key='Description',
            use_subtype=True,
            sender_id_key='Sender ID',
            receiver_id_key='Receiver ID',
            endpoint_param_key='pw_transaction_by_date_endpoint',
        )

    @api.model
    def cron_fetch_pw_visa_balance_entries(self, date=None, date_to=None):
        self.fetch_entries(
            transaction_type='Visa Balance',
            date=date,
            date_to=date_to,
            json_payload=True,
            transaction_list_name='TransactionList',
            trans_id_key='OrderID',
            amount_key='Amount',
            description_key='Description',
            use_subtype=True,
            sender_id_key='Sender ID',
            receiver_id_key='Receiver ID',
            endpoint_param_key='pw_transaction_by_date_endpoint',
        )

    @api.model
    def cron_fetch_pw_hala_transfer_entries(self, date=None, date_to=None):
        self.fetch_entries(
            transaction_type='Hala Transfer',
            date=date,
            date_to=date_to,
            json_payload=True,
            transaction_list_name='TransactionList',
            trans_id_key='OrderID',
            amount_key='Amount',
            description_key='Description',
            use_subtype=True,
            sender_id_key='Sender ID',
            receiver_id_key='Receiver ID',
            endpoint_param_key='pw_transaction_by_date_endpoint',
        )

    @api.model
    def cron_fetch_pw_new_balanced_entries(self, date=None, date_to=None):
        self.fetch_entries(
            transaction_type='New Balance',
            date=date,
            date_to=date_to,
            json_payload=True,
            transaction_list_name='TransactionList',
            trans_id_key='OrderID',
            amount_key='Amount',
            description_key='Description',
            use_subtype=False,
            endpoint_param_key='pw_new_balance_by_date_endpoint',
        )

    @api.model
    def cron_fetch_pw_receivables_entries(self, date=None, date_to=None):
        self.fetch_entries(
            transaction_type='Receivables',
            date=date,
            date_to=date_to,
            json_payload=True,
            transaction_list_name='receiptList',
            trans_id_key='receipt_ID',
            amount_key='Amount',
            description_key='Description',
            use_subtype=False,
            endpoint_param_key='pw_receivables_by_date_endpoint',
        )

    @api.model
    def cron_fetch_pw_mdr_transfer_entries(self, date=None, date_to=None):
        self.fetch_entries(
            transaction_type='MDR Transfer',
            date=date,
            date_to=date_to,
            json_payload=False,
            transaction_list_name='TransactionList',
            trans_id_key='ID',
            amount_key='Amount',
            description_key='payment_method',
            use_subtype=False,
            endpoint_param_key='pw_mdr_transfer_by_date_endpoint',
        )


    @api.model
    def cron_fetch_pw_commission_entries(self, date=None, date_to=None):
        self.fetch_entries(
            transaction_type='Commission',
            date=date,
            date_to=date_to,
            json_payload=True,
            transaction_list_name='CommissionList',
            trans_id_key='OrderID',
            amount_key='Amount',
            description_key='Operation',
            use_subtype=False,
            endpoint_param_key='pw_commission_transaction_by_date_endpoint',
        )

    @api.model
    def cron_fetch_pw_mada_profits_entries(self, date=None, date_to=None):
        self.fetch_entries(
            transaction_type='Mada Profits',
            date=date,
            date_to=date_to,
            json_payload=True,
            transaction_list_name='orderList',
            trans_id_key='order_id',
            amount_key='Mada_profits',
            description_key='Products',
            use_subtype=False,
            endpoint_param_key='pw_mada_wallet_profits_by_date_endpoint',
        )
