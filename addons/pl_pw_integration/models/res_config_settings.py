# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Default Accounts
    # New Balance
    new_balance_journal_id = fields.Many2one('account.journal', string='New Balance Journal',
                                             related='company_id.new_balance_journal_id', readonly=False)
    new_balance_credit_account_id = fields.Many2one('account.account', string='New Balance Credit Account',
                                                    related='company_id.new_balance_credit_account_id', readonly=False)
    new_balance_debit_account_id = fields.Many2one('account.account', string='New Balance Debit Account',
                                                   related='company_id.new_balance_debit_account_id', readonly=False)

    # Balanced Transfer
    balance_trns_rep_journal_id = fields.Many2one('account.journal', string='Journal From MDA to MDR',
                                                  related='company_id.balance_trns_rep_journal_id', readonly=False)
    balance_trns_rep_credit_account_id = fields.Many2one('account.account', string='Credit Account From MDA to MDR',
                                                         related='company_id.balance_trns_rep_credit_account_id',
                                                         readonly=False)
    balance_trns_rep_debit_account_id = fields.Many2one('account.account', string='Debit Account From MDA to MDR',
                                                        related='company_id.balance_trns_rep_debit_account_id',
                                                        readonly=False)

    balance_trns_pos_journal_id = fields.Many2one('account.journal', string='Journal From MDR to POS',
                                                  related='company_id.balance_trns_pos_journal_id', readonly=False)
    balance_trns_pos_credit_account_id = fields.Many2one('account.account', string='Credit Account From MDR to POS',
                                                         related='company_id.balance_trns_pos_credit_account_id',
                                                         readonly=False)
    balance_trns_pos_debit_account_id = fields.Many2one('account.account', string='Debit Account From MDR to POS',
                                                        related='company_id.balance_trns_pos_debit_account_id',
                                                        readonly=False)

    balance_trns_mda_journal_id = fields.Many2one('account.journal', string='Journal From MDA to POS',
                                                        related='company_id.balance_trns_mda_journal_id',
                                                        readonly=False)
    balance_trns_mda_credit_account_id = fields.Many2one('account.account', string='Credit Account From MDA to POS',
                                                        related='company_id.balance_trns_mda_credit_account_id',
                                                        readonly=False)
    balance_trns_mda_debit_account_id = fields.Many2one('account.account', string='Debit Account From MDA to POS',
                                                        related='company_id.balance_trns_mda_debit_account_id',
                                                        readonly=False)

    # Balance Pulled
    balance_pull_mda2mda_journal_id = fields.Many2one('account.journal', string='Balance Pulled Journal',
                                                      related='company_id.balance_pull_mda2mda_journal_id',
                                                      readonly=False)
    balance_pull_mda2mda_credit_account_id = fields.Many2one('account.account', string='Balance Pulled Credit Account',
                                                             related='company_id.balance_pull_mda2mda_credit_account_id',
                                                             readonly=False)
    balance_pull_mda2mda_debit_account_id = fields.Many2one('account.account', string='Balance Pulled Debit Account',
                                                            related='company_id.balance_pull_mda2mda_debit_account_id',
                                                            readonly=False)

    balance_pull_pos2mda_journal_id = fields.Many2one('account.journal', string='Balance Pulled Journal',
                                                      related='company_id.balance_pull_pos2mda_journal_id',
                                                      readonly=False)
    balance_pull_pos2mda_credit_account_id = fields.Many2one('account.account', string='Balance Pulled Credit Account',
                                                             related='company_id.balance_pull_pos2mda_credit_account_id',
                                                             readonly=False)
    balance_pull_pos2mda_debit_account_id = fields.Many2one('account.account', string='Balance Pulled Debit Account',
                                                            related='company_id.balance_pull_pos2mda_debit_account_id',
                                                            readonly=False)

    balance_pull_mdr2mda_journal_id = fields.Many2one('account.journal', string='Balance Pulled Journal',
                                                      related='company_id.balance_pull_mdr2mda_journal_id',
                                                      readonly=False)
    balance_pull_mdr2mda_credit_account_id = fields.Many2one('account.account', string='Balance Pulled Credit Account',
                                                             related='company_id.balance_pull_mdr2mda_credit_account_id',
                                                             readonly=False)
    balance_pull_mdr2mda_debit_account_id = fields.Many2one('account.account', string='Balance Pulled Debit Account',
                                                            related='company_id.balance_pull_mdr2mda_debit_account_id',
                                                            readonly=False)

    # Visa Balance
    visa_balance_journal_id = fields.Many2one('account.journal', string='Visa Balance Journal',
                                              related='company_id.visa_balance_journal_id', readonly=False)
    visa_balance_credit_account_id = fields.Many2one('account.account', string='Visa Balance Credit Account',
                                                     related='company_id.visa_balance_credit_account_id',
                                                     readonly=False)
    visa_balance_debit_account_id = fields.Many2one('account.account', string='Visa Balance Debit Account',
                                                    related='company_id.visa_balance_debit_account_id', readonly=False)
    visa_balance_sec_credit_account_id = fields.Many2one('account.account', string='2nd Visa Balance Credit Account',
                                                         related='company_id.visa_balance_sec_credit_account_id',
                                                         readonly=False)
    visa_balance_sec_debit_account_id = fields.Many2one('account.account', string='2nd Visa Balance Debit Account',
                                                        related='company_id.visa_balance_sec_debit_account_id',
                                                        readonly=False)

    # Commission
    commission_journal_id = fields.Many2one('account.journal', string='Commission Journal',
                                                 related='company_id.commission_journal_id', readonly=False)
    commission_credit_account_id = fields.Many2one('account.account', string='Commission Credit Account',
                                                        related='company_id.commission_credit_account_id',
                                                        readonly=False)
    commission_debit_account_id = fields.Many2one('account.account', string='Commission Debit Account',
                                                       related='company_id.commission_debit_account_id',
                                                       readonly=False)

    # Hala Transfer
    hala_trans_journal_id = fields.Many2one('account.journal', string='Hala Transfer Journal',
                                            related='company_id.hala_trans_journal_id', readonly=False)
    hala_trans_credit_account_id = fields.Many2one('account.account', string='Hala Transfer Credit Account',
                                                   related='company_id.hala_trans_credit_account_id', readonly=False)
    hala_trans_debit_account_id = fields.Many2one('account.account', string='Hala Transfer Debit Account',
                                                  related='company_id.hala_trans_debit_account_id', readonly=False)
    hala_trans_sec_credit_account_id = fields.Many2one('account.account', string='2nd Hala Transfer Credit Account',
                                                       related='company_id.hala_trans_sec_credit_account_id',
                                                       readonly=False)
    hala_trans_sec_debit_account_id = fields.Many2one('account.account', string='2nd Hala Transfer Debit Account',
                                                      related='company_id.hala_trans_sec_debit_account_id',
                                                      readonly=False)

    # POS Receivables
    pos_receivables_journal_id = fields.Many2one('account.journal', string='POS Receivables Journal',
                                                 related='company_id.pos_receivables_journal_id',
                                                 readonly=False)
    pos_receivables_credit_account_id = fields.Many2one('account.account', string='POS Receivables Credit Account',
                                                        related='company_id.pos_receivables_credit_account_id',
                                                        readonly=False)
    pos_receivables_debit_account_id = fields.Many2one('account.account', string='POS Receivables Debit Account',
                                                       related='company_id.pos_receivables_debit_account_id',
                                                       readonly=False)
    pos_receivables_sec_credit_account_id = fields.Many2one('account.account',
                                                            string='2nd POS Receivables Credit Account',
                                                       related='company_id.pos_receivables_sec_credit_account_id',
                                                       readonly=False)
    pos_receivables_sec_debit_account_id = fields.Many2one('account.account',
                                                           string='2nd POS Receivables Debit Account',
                                                       related='company_id.pos_receivables_sec_debit_account_id',
                                                       readonly=False)

    # MDR Transfer
    mdr_transfer_journal_id = fields.Many2one('account.journal', string='MDR Transfer Journal',
                                              related='company_id.mdr_transfer_journal_id',
                                              readonly=False)
    mdr_transfer_credit_account_id = fields.Many2one('account.account', string='MDR Transfer Credit Account',
                                                     related='company_id.mdr_transfer_credit_account_id',
                                                     readonly=False)
    mdr_transfer_debit_account_id = fields.Many2one('account.account', string='MDR Transfer Debit Account',
                                                    related='company_id.mdr_transfer_debit_account_id',
                                                    readonly=False)

    # Mada Profit
    mada_profit_journal_id = fields.Many2one('account.journal', string='Mada Profits Transfer Journal',
                                              related='company_id.mada_profit_journal_id',
                                              readonly=False)
    mada_profit_credit_account_id = fields.Many2one('account.account', string='Mada Profits Credit Account',
                                              related='company_id.mada_profit_credit_account_id',
                                              readonly=False)
    mada_profit_debit_account_id = fields.Many2one('account.account', string='Mada Profits Debit Account',
                                              related='company_id.mada_profit_debit_account_id',
                                              readonly=False)

    # Stock Operations
    robo_pw_operation_id = fields.Many2one('stock.picking.type', string='Robo to PW Operation',
                                           related='company_id.robo_pw_operation_id',
                                           readonly=False)
    other_operation_id = fields.Many2one('stock.picking.type', string='Offline Operation',
                                         related='company_id.other_operation_id',
                                         readonly=False)
    online_operation_id = fields.Many2one('stock.picking.type', string='Online Operation',
                                         related='company_id.online_operation_id',
                                         readonly=False)
