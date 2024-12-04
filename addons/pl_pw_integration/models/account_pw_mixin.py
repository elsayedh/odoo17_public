from odoo import fields, models, api, _
import requests
from datetime import timedelta
import json
from collections import defaultdict
import logging

_logger = logging.getLogger(__name__)


class AccountPWMixin(models.AbstractModel):
    _name = 'account.pw.mixin'
    _description = 'Account PW Mixin'

    pw_id = fields.Char(string='PW ID', index=True)

    def fetch_entries(self, batch_size=5000, retry_limit=3, **kwargs):
        """
        Fetches entries for specified transaction types and dates from external API for multiple companies.

        Args:
            batch_size: Number of entries to process at once for batch insert (default 1000).
            retry_limit: Number of retry attempts in case of failure (default 3).
            **kwargs: Arbitrary keyword arguments to customize the fetch process.

        Returns:
            None
        """
        companies = self.env['res.company'].search([('pw_access_token', '!=', False)])
        if not companies:
            _logger.info(_('No companies found with a valid access token.'))
            return

        # Default date range
        date_from = fields.Date.from_string(kwargs.get('date')) if kwargs.get(
            'date') else fields.Date.today() - timedelta(days=1)
        date_to = fields.Date.from_string(kwargs.get('date_to')) if kwargs.get('date_to') else date_from

        for company in companies:

            entry_vals = []

            while date_from <= date_to:
                fetch_date = date_from

                url = self.env['ir.config_parameter'].sudo().get_param(kwargs['endpoint_param_key'])
                payload = self._prepare_payload(fetch_date, kwargs['transaction_type'], kwargs.get('json_payload'))
                headers = self._prepare_headers(company, kwargs.get('json_payload'))

                # Fetch transactions in batch with retry mechanism
                transactions = self._fetch_transactions_with_retry(url, headers, payload, kwargs['transaction_type'],
                                                                   kwargs['transaction_list_name'], fetch_date,
                                                                   retry_limit)
                if not transactions:
                    date_from += timedelta(days=1)
                    continue

                # Prepare entries for batch processing
                entry_vals += self._prepare_entries(transactions, company, kwargs, fetch_date)

                date_from += timedelta(days=1)

            if entry_vals:
                self._process_entries_in_batches(entry_vals, company, batch_size, kwargs['transaction_type'],
                                                 kwargs.get('date') or date_from, kwargs.get('date_to') or date_to)

    def _prepare_payload(self, fetch_date, transaction_type, json_payload):
        """ Prepares the API request payload. """
        if json_payload:
            return json.dumps({"Date": str(fetch_date), "Operation_Type": transaction_type})
        return "{\r\n  \"Date\": \"%s\"\r\n}" % str(fetch_date)

    def _prepare_headers(self, company, json_payload):
        """ Prepares the headers for the API request. """
        return {
            'Token': company.pw_access_token,
            'Content-Type': 'application/json' if json_payload else 'text/plain'
        }

    def _fetch_transactions_with_retry(self, url, headers, payload, transaction_type, transaction_list_name, fetch_date,
                                       retry_limit):
        """
        Fetches transactions from the external API with a retry mechanism.

        Args:
            retry_limit: Maximum number of retry attempts.

        Returns:
            list: The list of transactions, or None if failed after retries.
        """
        retries = 0
        while retries < retry_limit:
            try:
                return self._fetch_transactions(url, headers, payload, transaction_type, transaction_list_name,
                                                fetch_date)
            except Exception as e:
                retries += 1
                if retries < retry_limit:
                    _logger.warning(
                        f"Retrying API request ({retries}/{retry_limit}) for {transaction_type} on {fetch_date}")
                else:
                    _logger.error(
                        f"Failed after {retry_limit} attempts for {transaction_type} on {fetch_date}: {str(e)}")
                    return None

    def _fetch_transactions(self, url, headers, payload, transaction_type, transaction_list_name, fetch_date):
        """
        Fetches transactions from the external API.

        Returns:
            list: List of transactions.
        """
        msg = _('Starting to fetch %s entries of %s' % (transaction_type, fetch_date))
        self._action_log(msg, log_type='info')
        _logger.info(msg)

        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()  # Raise error for non-200 responses
        json_data = response.json()

        if not isinstance(json_data, list) or not json_data:
            _logger.info(_('No transactions found for %s on %s'), transaction_type, fetch_date)
            return []

        return json_data[0].get(transaction_list_name, [])

    def _prepare_entries(self, transactions, company, kwargs, fetch_date):
        """
        Prepares the account move line entries from the fetched transactions.

        Returns:
            list: A list of prepared entry values.
        """
        entry_vals = []
        for trans in transactions:
            try:
                if self._is_pw_entry_exist(trans.get(kwargs['trans_id_key'])):
                    _logger.info(_('Transaction %s already exists'), trans.get(kwargs['trans_id_key']))
                    continue

                subtype = '{sender}2{receiver}'.format(sender=trans[kwargs['sender_id_key']][:3],
                                                       receiver=trans[kwargs['receiver_id_key']][:3]) if kwargs.get(
                    'use_subtype') else 'None2None'

                entry_vals += self._prepare_pw_entry(company, kwargs, trans, fetch_date, subtype)
                _logger.info(_('Prepared entry for transaction %s (%s)'), kwargs['transaction_type'],
                             trans.get(kwargs['trans_id_key']))

            except Exception as e:
                msg = f"Error preparing entry for {kwargs['transaction_type']} on {fetch_date}: {str(e)}"
                self._action_log(msg, log_type='error', pw_order_id=trans.get(kwargs['trans_id_key']))
                _logger.error(msg)

        return entry_vals

    def _process_entries_in_batches(self, entry_vals, company, batch_size, transaction_type, from_date, to_date):
        """
        Processes and posts entries in batches.

        Args:
            batch_size: Number of entries to insert at once for better performance.

        Returns:
            None
        """
        total_entries = len(entry_vals)
        total_posted_entries = 0
        i = 0

        while i < total_entries:
            # Start with the default batch size
            batch = entry_vals[i:i + batch_size]

            # Temporary index to track how far to extend the batch
            temp_index = i + batch_size

            # Extend the batch if the last item in the current batch and the first item in the next batch share the same move_id
            while temp_index < total_entries and batch[-1]['move_id'] == entry_vals[temp_index]['move_id']:
                batch.append(entry_vals[temp_index])  # Add the next item with the same move_id to the batch
                temp_index += 1  # Move the index forward

            # Update total posted entries count
            total_posted_entries += len(batch)

            try:
                # Insert entries in the current batch
                self._insert_pw_aml(batch, company)

                move_ids = self.sudo().browse([val['move_id'] for val in batch])

                # Recompute and post the entries
                self._recompute_fields(move_ids)
                move_ids.action_post()

                msg = _('Successfully fetched and posted %s/%s entries for %s from %s to %s') % (
                    total_posted_entries, total_entries, transaction_type, from_date, to_date)
                self._action_log(msg, log_type='info')
                _logger.info(msg)

            except Exception as e:
                msg = f"Error processing entries for {transaction_type} from {from_date} to {to_date}: {str(e)}"
                self._action_log(msg, log_type='error')
                _logger.error(msg)
                # Rollback in case of failure in batch
                self.env.cr.rollback()

            # Move the index forward based on the extended batch size, but keep the batch_size constant for future loops
            i = temp_index

    def _recompute_fields(self, move_ids):
        self.env.add_to_compute(move_ids.line_ids._fields['price_subtotal'], move_ids.line_ids)
        self.env.add_to_compute(move_ids.line_ids._fields['price_total'], move_ids.line_ids)
        self.env.add_to_compute(move_ids.line_ids._fields['balance'], move_ids.line_ids)
        self.env.add_to_compute(move_ids.line_ids._fields['amount_currency'], move_ids.line_ids)

        self.env.add_to_compute(move_ids._fields['amount_untaxed'], move_ids)
        self.env.add_to_compute(move_ids._fields['amount_tax'], move_ids)
        self.env.add_to_compute(move_ids._fields['amount_total'], move_ids)
        self.env.add_to_compute(move_ids._fields['amount_residual'], move_ids)
        self.env.add_to_compute(move_ids._fields['amount_untaxed_signed'], move_ids)
        self.env.add_to_compute(move_ids._fields['amount_tax_signed'], move_ids)
        self.env.add_to_compute(move_ids._fields['amount_total_signed'], move_ids)
        self.env.add_to_compute(move_ids._fields['amount_total_in_currency_signed'], move_ids)
        self.env.add_to_compute(move_ids._fields['amount_residual_signed'], move_ids)

    def _insert_pw_aml(self, lines, company_id):
        try:
            query = '''
                        INSERT INTO account_move_line (name, 
                        credit, 
                        debit, 
                        account_id, 
                        partner_id, 
                        move_id, 
                        currency_id, 
                        display_type, 
                        company_id, 
                        journal_id,
                        quantity,
                        amount_currency,
                        balance) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    '''

            values = [
                (line['name'],
                 line.get('credit', 0),
                 line.get('debit', 0),
                 line['account_id'],
                 line['partner_id'] or None,
                 line['move_id'],
                 company_id.currency_id.id,
                 'product',
                 company_id.id,
                 line['journal_id'],
                 1.0,
                 -line.get('credit', 0.0) or line.get('debit', 0.0),
                 -line.get('credit', 0.0) or line.get('debit', 0.0))
                for line in lines]

            # Execute the query using batch inserts
            self.env.cr.executemany(query, values)

            # Commit the transaction to save the changes
            self.env.cr.commit()

        except Exception as e:
            # Rollback in case of an error
            self.env.cr.rollback()
            _logger.error("Error inserting account move lines: %s", e)

    def _entry_default_values(self):
        return ('draft', 'no', 'no_extract_requested')

    def _prepare_pw_entry(self, company, transaction_details, vals, date, subtype):
        defaults = company.get_pw_transactions_defaults(transaction_details['transaction_type'], subtype, vals)
        if not defaults:
            self._action_log(_('No default accounts for %s' % transaction_details['transaction_type']), log_type='error')
            return

        partners = self._get_partner_by_pw_id(vals, transaction_details['transaction_type'], subtype)

        query = '''
            INSERT INTO account_move (move_type, 
            journal_id, 
            date, 
            ref, 
            pw_id, 
            company_id, 
            currency_id, 
            state, 
            auto_post, 
            extract_state)
            VALUES ('entry', %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        '''

        try:
            self.env.cr.execute(query, (
                defaults['journal_id'],
                date, vals.get('OrderID') or vals.get('receipt_ID') or vals.get('ID'),
                vals.get('OrderID') or vals.get('receipt_ID') or vals.get('ID'),
                company.id,
                company.currency_id.id,
                *self._entry_default_values()))

            move_id = self.env.cr.fetchone()[0]

            # Commit the transaction to save the changes
            self.env.cr.commit()

            return self._prepare_pw_entry_lines(move_id, transaction_details, vals, defaults, partners)

        except Exception as e:
            # Rollback in case of an error
            self.env.cr.rollback()
            _logger.error("Error create entry: %s", e)

    def _prepare_pw_entry_lines(self, move_id, transaction_details, vals, defaults, partners):
        aml = []
        aml.append({
            'name': vals.get(transaction_details['description_key']) or transaction_details['transaction_type'],
            'credit': float(vals[transaction_details['amount_key']]),
            'account_id': defaults['credit_account_id'],
            'partner_id': partners['credit'],
            'move_id': move_id,
            'journal_id': defaults['journal_id']
        })

        aml.append({
            'name': vals.get(transaction_details['description_key']) or transaction_details['transaction_type'],
            'debit': float(vals[transaction_details['amount_key']]),
            'account_id': defaults['debit_account_id'],
            'partner_id': partners['debit'],
            'move_id': move_id,
            'journal_id': defaults['journal_id']
        })

        if '2nd_credit_account_id' in defaults and '2nd_debit_account_id' in defaults:
            aml.append({
                'name': vals.get(transaction_details['description_key']) or transaction_details['transaction_type'],
                'credit': float(vals[transaction_details['amount_key']]),
                'account_id': defaults['2nd_credit_account_id'],
                'partner_id': partners['credit2'],
                'move_id': move_id,
                'journal_id': defaults['journal_id']
            })

            aml.append({
                'name': vals.get(transaction_details['description_key']) or transaction_details['transaction_type'],
                'debit': float(vals[transaction_details['amount_key']]),
                'account_id': defaults['2nd_debit_account_id'],
                'partner_id': partners['debit2'],
                'move_id': move_id,
                'journal_id': defaults['journal_id']
            })

        return aml

    def _is_pw_entry_exist(self, pw_id=None):
        # Check if entry is existing
        query = """
                    SELECT id
                    FROM account_move 
                    WHERE pw_id = %s
                """

        self.env.cr.execute(query, (pw_id,))
        result = self.env.cr.fetchall()

        if result:
            _logger.error(_('Entry with same PW id: %s already exists'), pw_id)
            return True

        return False

    def _get_partner_by_pw_id(self, vals, transaction_type, transfer_type):
        partners = defaultdict(credit=False, debit=False, credit2=False, debit2=False)
        sender, receiver = transfer_type.split('2')

        if transaction_type == 'New Balance':
            partners['debit'] = self._get_entry_partner('MDA', vals['Receiver ID'])
            return partners

        if transaction_type in ('Balanced transfer', 'balance pulled'):
            partners['credit'] = self._get_entry_partner(sender, vals['Sender ID'], posmdr=True)
            partners['debit'] = self._get_entry_partner(receiver, vals['Receiver ID'], posmdr=True)
            return partners

        if transaction_type in ('Visa Balance', 'Hala Transfer'):
            partners['credit'] = self._get_entry_partner(sender, vals['Sender ID'])
            partners['credit2'] = self._get_entry_partner(receiver, vals['Receiver ID'])
            return partners

        if transaction_type == 'Receivables':
            partners['credit'] = self._get_entry_partner('POS', vals['PayerID'])
            partners['credit2'] = partners['debit2'] = self._get_entry_partner('MDR', vals['PayeeID'])
            return partners

        if transaction_type == 'MDR Transfer':
            partners['credit'] = self._get_entry_partner('MDR', vals['Rep_ID'])
            return partners

        if transaction_type == 'Commission':
            partners['credit'] = self._get_entry_partner('POS', vals['UserID'])
            return partners

        return partners

    def _get_entry_partner(self, partner_type, pw_id, posmdr=False):
        pw_id = pw_id.upper()  # Convert PW code to capital case
        if partner_type == 'POS':
            if posmdr:
                # In case POS is the partner but the transaction isn't receivable the partner here is the sales person that is related to the POS partner
                query = '''
                    SELECT rp2.id
                    FROM res_partner rp
                    JOIN res_users ru ON ru.id = rp.user_id
                    JOIN res_partner rp2 ON rp2.id = ru.partner_id
                    WHERE rp.pw_pos_id = %s
                    LIMIT 1;
                '''

            else:
                query = '''
                    SELECT id
                    FROM res_partner
                    WHERE pw_pos_id = %s
                    LIMIT 1;
                '''

        else:
            query = '''
                SELECT partner_id
                FROM res_users
                WHERE pw_id = %s
                LIMIT 1;
            '''

        self.env.cr.execute(query, (pw_id,))
        result = self.env.cr.fetchall()

        return result[0] if result else False

    def _action_log(self, desc, log_type, pw_order_id=False):
        self.env['pw.log'].sudo().create({
            'date': fields.datetime.now(),
            'name': desc,
            'pw_id': pw_order_id,
            'log_type': log_type
        })
