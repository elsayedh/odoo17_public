# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import requests
import json
from odoo.exceptions import ValidationError


class Company(models.Model):
    _inherit = 'res.company'

    pw_user = fields.Char('User')
    pw_password = fields.Char('Password')
    pw_access_token = fields.Char('Access Token')

    # Default Accounts
    # New Balance
    new_balance_journal_id = fields.Many2one('account.journal', string='New Balance Journal')
    new_balance_credit_account_id = fields.Many2one('account.account', string='New Balance Credit Account')
    new_balance_debit_account_id = fields.Many2one('account.account', string='New Balance Debit Account')

    # Balanced Transfer
    balance_trns_rep_journal_id = fields.Many2one('account.journal', string='Journal From MDA to MDR')
    balance_trns_rep_credit_account_id = fields.Many2one('account.account', string='Credit Account From MDA to MDR')
    balance_trns_rep_debit_account_id = fields.Many2one('account.account', string='Debit Account From MDA to MDR')

    balance_trns_pos_journal_id = fields.Many2one('account.journal', string='Journal From MDR to POS')
    balance_trns_pos_credit_account_id = fields.Many2one('account.account', string='Credit Account From MDR to POS')
    balance_trns_pos_debit_account_id = fields.Many2one('account.account', string='Debit Account From MDR to POS')

    balance_trns_mda_journal_id = fields.Many2one('account.journal', string='Journal From MDA to POS')
    balance_trns_mda_credit_account_id = fields.Many2one('account.account', string='Credit Account From MDA to POS')
    balance_trns_mda_debit_account_id = fields.Many2one('account.account', string='Debit Account From MDA to POS')

    # Balance Pulled
    balance_pull_mda2mda_journal_id = fields.Many2one('account.journal', string='Balance Pulled MDA 2 MDA Journal')
    balance_pull_mda2mda_credit_account_id = fields.Many2one('account.account',
                                                             string='Balance Pulled Credit MDA 2 MDA Account')
    balance_pull_mda2mda_debit_account_id = fields.Many2one('account.account',
                                                            string='Balance Pulled Debit MDA 2 MDA Account')

    balance_pull_pos2mda_journal_id = fields.Many2one('account.journal', string='Balance Pulled POS 2 MDA Journal')
    balance_pull_pos2mda_credit_account_id = fields.Many2one('account.account',
                                                             string='Balance Pulled Credit POS 2 MDA Account')
    balance_pull_pos2mda_debit_account_id = fields.Many2one('account.account',
                                                            string='Balance Pulled Debit POS 2 MDA Account')

    balance_pull_mdr2mda_journal_id = fields.Many2one('account.journal', string='Balance Pulled MDR 2 MDA Journal')
    balance_pull_mdr2mda_credit_account_id = fields.Many2one('account.account',
                                                             string='Balance Pulled Credit MDR 2 MDA Account')
    balance_pull_mdr2mda_debit_account_id = fields.Many2one('account.account',
                                                            string='Balance Pulled Debit MDR 2 MDA Account')

    # Visa Balance
    visa_balance_journal_id = fields.Many2one('account.journal', string='Visa Balance Journal')
    visa_balance_credit_account_id = fields.Many2one('account.account', string='Visa Balance Credit Account')
    visa_balance_debit_account_id = fields.Many2one('account.account', string='Visa Balance Debit Account')
    visa_balance_sec_credit_account_id = fields.Many2one('account.account', string='2nd Visa Balance Credit Account')
    visa_balance_sec_debit_account_id = fields.Many2one('account.account', string='2nd Visa Balance Debit Account')

    # Commission
    commission_journal_id = fields.Many2one('account.journal', string='Commission Journal')
    commission_credit_account_id = fields.Many2one('account.account', string='Commission Credit Account')
    commission_debit_account_id = fields.Many2one('account.account', string='Commission Debit Account')

    # Hala Transfer
    hala_trans_journal_id = fields.Many2one('account.journal', string='Hala Transfer Journal')
    hala_trans_credit_account_id = fields.Many2one('account.account', string='Hala Transfer Credit Account')
    hala_trans_debit_account_id = fields.Many2one('account.account', string='Hala Transfer Debit Account')
    hala_trans_sec_credit_account_id = fields.Many2one('account.account', string='2nd Hala Transfer Credit Account')
    hala_trans_sec_debit_account_id = fields.Many2one('account.account', string='2nd Hala Transfer Debit Account')

    # POS Receivables
    pos_receivables_journal_id = fields.Many2one('account.journal', string='POS Receivables Journal')
    pos_receivables_credit_account_id = fields.Many2one('account.account', string='POS Receivables Credit Account')
    pos_receivables_debit_account_id = fields.Many2one('account.account', string='POS Receivables Debit Account')
    pos_receivables_sec_credit_account_id = fields.Many2one('account.account',
                                                            string='2nd POS Receivables Credit Account')
    pos_receivables_sec_debit_account_id = fields.Many2one('account.account',
                                                           string='2nd POS Receivables Debit Account')

    # MDR Transfer
    mdr_transfer_journal_id = fields.Many2one('account.journal', string='MDR Transfer Journal')
    mdr_transfer_credit_account_id = fields.Many2one('account.account', string='MDR Transfer Credit Account')
    mdr_transfer_debit_account_id = fields.Many2one('account.account', string='MDR Transfer Debit Account',
                                                    help='Will use this account as a default in case no account in chart has the PW account number')

    # Mada Profit
    mada_profit_journal_id = fields.Many2one('account.journal', string='Mada Profit Transfer Journal')
    mada_profit_credit_account_id = fields.Many2one('account.account', string='Mada Profit Credit Account')
    mada_profit_debit_account_id = fields.Many2one('account.account', string='Mada Profit Debit Account')

    # Stock Operations
    robo_pw_operation_id = fields.Many2one('stock.picking.type', string='Robo Operation')
    other_operation_id = fields.Many2one('stock.picking.type', string='Offline Operation')
    online_operation_id = fields.Many2one('stock.picking.type', string='Online Operation')

    def action_pw_connect(self):
        login_url = self.env['ir.config_parameter'].sudo().get_param('pw_login_endpoint')
        if not login_url:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'danger',
                    'message': _("Undefined login URL."),
                }
            }

        payload = '{\r\n  \"userid\": \"%s\",\r\n  \"Password\": \"%s\"\r\n}' % (self.pw_user, self.pw_password)
        headers = {
            'Content-Type': 'text/plain'
        }

        response = requests.request("POST", login_url, headers=headers, data=payload)

        json_data = json.loads(response.text)
        if not json_data or not json_data[0].get('isSuccess', False) or not json_data[0].get('token', False):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'danger',
                    'message': _("PW failed to connect or may user/password is wrong."),
                }
            }

        self.write({
            'pw_access_token': json_data[0].get('token')
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _("PW successfully connected."),
            }
        }

    def get_pw_transactions_defaults(self, type, subtype, vals):
        if type == 'Balanced transfer':
            if subtype == 'MDA2MDR':
                return {
                    'journal_id': self.balance_trns_rep_journal_id.id,
                    'credit_account_id': self.balance_trns_rep_credit_account_id.id,
                    'debit_account_id': self.balance_trns_rep_debit_account_id.id
                }
            elif subtype == 'MDR2POS':
                return {
                    'journal_id': self.balance_trns_pos_journal_id.id,
                    'credit_account_id': self.balance_trns_pos_credit_account_id.id,
                    'debit_account_id': self.balance_trns_pos_debit_account_id.id
                }

            elif subtype == 'MDA2POS':
                return {
                    'journal_id': self.balance_trns_mda_journal_id.id,
                    'credit_account_id': self.balance_trns_mda_credit_account_id.id,
                    'debit_account_id': self.balance_trns_mda_debit_account_id.id
                }

        elif type == 'balance pulled':
            if subtype == 'MDA2MDA':
                return {
                    'journal_id': self.balance_pull_mda2mda_journal_id.id,
                    'credit_account_id': self.balance_pull_mda2mda_credit_account_id.id,
                    'debit_account_id': self.balance_pull_mda2mda_debit_account_id.id
                }
            elif subtype == 'POS2MDA':
                return {
                    'journal_id': self.balance_pull_pos2mda_journal_id.id,
                    'credit_account_id': self.balance_pull_pos2mda_credit_account_id.id,
                    'debit_account_id': self.balance_pull_pos2mda_debit_account_id.id
                }
            elif subtype == 'MDR2MDA':
                return {
                    'journal_id': self.balance_pull_mdr2mda_journal_id.id,
                    'credit_account_id': self.balance_pull_mdr2mda_credit_account_id.id,
                    'debit_account_id': self.balance_pull_mdr2mda_debit_account_id.id
                }

        elif type == 'Visa Balance':
            return {
                'journal_id': self.visa_balance_journal_id.id,
                'credit_account_id': self.visa_balance_credit_account_id.id,
                'debit_account_id': self.visa_balance_debit_account_id.id,
                '2nd_credit_account_id': self.visa_balance_sec_credit_account_id.id,
                '2nd_debit_account_id': self.visa_balance_sec_debit_account_id.id
            }

        elif type == 'Commission':
            return {
                'journal_id': self.commission_journal_id.id,
                'credit_account_id': self.commission_credit_account_id.id,
                'debit_account_id': self.commission_debit_account_id.id
            }

        elif type == 'New Balance':
            return {
                'journal_id': self.new_balance_journal_id.id,
                'credit_account_id': self.new_balance_credit_account_id.id,
                'debit_account_id': self.new_balance_debit_account_id.id
            }

        elif type == 'Hala Transfer':
            return {
                'journal_id': self.hala_trans_journal_id.id,
                'credit_account_id': self.hala_trans_credit_account_id.id,
                'debit_account_id': self.hala_trans_debit_account_id.id,
                '2nd_credit_account_id': self.hala_trans_sec_credit_account_id.id,
                '2nd_debit_account_id': self.hala_trans_sec_debit_account_id.id
            }

        elif type == 'Receivables':
            return {
                'journal_id': self.pos_receivables_journal_id.id,
                'credit_account_id': self.pos_receivables_credit_account_id.id,
                'debit_account_id': self.pos_receivables_debit_account_id.id,
                '2nd_credit_account_id': self.pos_receivables_sec_credit_account_id.id,
                '2nd_debit_account_id': self.pos_receivables_sec_debit_account_id.id
            }

        elif type == 'MDR Transfer':
            if vals and vals.get('Account_Number'):
                debit_account_id = self.env['account.account'].get_pw_account(
                    vals['Account_Number']) or self.mdr_transfer_debit_account_id

            else:
                debit_account_id = self.mdr_transfer_debit_account_id

            return {
                'journal_id': self.mdr_transfer_journal_id.id,
                'credit_account_id': self.mdr_transfer_credit_account_id.id,
                'debit_account_id': debit_account_id.id
            }

        elif type == 'Mada Profits':
            return {
                'journal_id': self.mada_profit_journal_id.id,
                'credit_account_id': self.mada_profit_credit_account_id.id,
                'debit_account_id': self.mada_profit_debit_account_id.id
            }

        else:
            return {}
