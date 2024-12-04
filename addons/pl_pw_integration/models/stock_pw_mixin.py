from odoo import fields, models, api, _
import requests
from datetime import timedelta
import json
import logging
from itertools import chain

_logger = logging.getLogger(__name__)


class StockPWMixin(models.AbstractModel):
    _name = 'stock.pw.mixin'
    _description = 'Stock PW Mixin'

    pw_id = fields.Char(string='PW ID')

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
                payload = self._prepare_payload(fetch_date, kwargs['order_type'], kwargs.get('json_payload'))
                headers = self._prepare_headers(company, kwargs.get('json_payload'))

                # Fetch transactions in batch with retry mechanism
                transactions = self._fetch_transactions_with_retry(url, headers, payload, kwargs['order_type'],
                                                                   kwargs['transaction_list_name'], fetch_date,
                                                                   retry_limit)
                if not transactions:
                    date_from += timedelta(days=1)
                    continue

                # Prepare entries for batch processing
                pw_id = self._generate_pw_id(kwargs['order_type'], fetch_date)
                entry_vals += self._prepare_online_order(transactions, fetch_date, pw_id, company)

                date_from += timedelta(days=1)

            if entry_vals:
                self._process_orders_in_batches(entry_vals, company, batch_size, kwargs['order_type'],
                                                kwargs.get('date') or date_from, kwargs.get('date_to') or date_to)

    def _fetch_transactions_with_retry(self, url, headers, payload, order_type, transaction_list_name, fetch_date,
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
                return self._fetch_transactions(url, headers, payload, order_type, transaction_list_name,
                                                fetch_date)
            except Exception as e:
                retries += 1
                if retries < retry_limit:
                    _logger.warning(
                        f"Retrying API request ({retries}/{retry_limit}) for {order_type} on {fetch_date}")
                else:
                    _logger.error(
                        f"Failed after {retry_limit} attempts for {order_type} on {fetch_date}: {str(e)}")
                    return None

    def _fetch_transactions(self, url, headers, payload, order_type, transaction_list_name, fetch_date):
        """
        Fetches transactions from the external API.

        Returns:
            list: List of transactions.
        """
        msg = _('Starting to fetch %s orders of %s' % (order_type, fetch_date))
        self._action_log(msg, log_type='info')
        _logger.info(msg)

        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()  # Raise error for non-200 responses
        json_data = response.json()

        if not isinstance(json_data, list) or not json_data:
            _logger.info(_('No transactions found for %s on %s'), order_type, fetch_date)
            return []

        return json_data[0].get(transaction_list_name, [])

    def _process_orders_in_batches(self, order_vals, company, batch_size, order_type, from_date, to_date):
        """
        Processes and posts entries in batches.

        Args:
            batch_size: Number of entries to insert at once for better performance.

        Returns:
            None
        """
        total_orders = len(order_vals)
        total_posted_orders = 0
        i = 0

        while i < total_orders:
            # Start with the default batch size
            batch = order_vals[i:i + batch_size]

            # Temporary index to track how far to extend the batch
            temp_index = i + batch_size

            # Extend the batch if the last item in the current batch and the first item in the next batch share the same order_id
            while temp_index < total_orders and batch[-1]['picking_id'].id == order_vals[temp_index]['picking_id'].id:
                batch.append(order_vals[temp_index])  # Add the next item with the same order_id to the batch
                temp_index += 1  # Move the index forward

            # Update total posted orders count
            total_posted_orders += len(batch)

            try:
                # Insert orders in batches
                self._insert_move_line(batch, company)

                picking_ids = self
                for val in batch:
                    picking_ids |= val['picking_id']

                # # Recompute and post the orders
                # self._recompute_fields(order_ids)

                # picking_ids.sudo().write({
                #     'date_done':
                # })

                # FIXME: issue in confirming the pickings
                picking_ids.sudo().action_confirm()
                picking_ids.sudo().button_validate()

                msg = _('Successfully fetched and posted %s/%s orders for %s from %s to %s') % (
                    total_posted_orders, total_orders, order_type, from_date, to_date)
                self._action_log(msg, log_type='info')
                _logger.info(msg)

            except Exception as e:
                msg = f"Error processing orders for %s from %s to %s: %s" % (
                    order_type, from_date, to_date, str(e))
                self._action_log(msg, log_type='error')
                _logger.error(msg)
                # Rollback in case of failure in batch
                self.env.cr.rollback()

            # Move the index forward based on the extended batch size, but keep the batch_size constant for future loops
            i = temp_index

    def _prepare_payload(self, fetch_date, transaction_type, json_payload):
        """ Prepares the API request payload. """
        if json_payload:
            return json.dumps({"Date": str(fetch_date)})
        return "{\r\n  \"Date\": \"%s\"\r\n}" % str(fetch_date)

    def _prepare_headers(self, company, json_payload):
        """ Prepares the headers for the API request. """
        return {
            'Token': company.pw_access_token,
            'Content-Type': 'application/json' if json_payload else 'text/plain'
        }

    def _prepare_online_order(self, orders, date, pw_id, company):
        # Check if order is existing
        query = """
            SELECT stock.id
            FROM stock_picking stock
            WHERE stock.pw_id = %s 
            AND stock.state != 'cancel'
        """

        self.env.cr.execute(query, (pw_id,))
        result = self.env.cr.fetchall()

        if result:
            _logger.error(_('Transaction with same ID: %s already exists'), pw_id)
            return

        picking_id = self.env['stock.picking'].with_company(company.id).create({
            'picking_type_id': self._get_picking_type_id('online', company).id,
            'scheduled_date': date,
            'date_done': date,
            'date_deadline': date,
            'pw_id': pw_id,
        })

        move_lines = list(chain.from_iterable(
            records for store_data in orders
            for store, dates in store_data.items()
            for date, records in dates.items()
        ))

        for line in move_lines:
            line['picking_id'] = picking_id

        _logger.info(_('Order %s was prepared' % pw_id))

        return move_lines

    @api.model
    def _insert_move_line(self, lines, company):
        try:
            query = """
                    INSERT INTO stock_move (product_id, product_uom_qty, quantity, name, product_uom, location_id, location_dest_id, picking_id, company_id, procure_method, date)
                    SELECT 
                        COALESCE(
                            (SELECT p.id FROM product_product p 
                             JOIN product_template pt ON pt.id = p.product_tmpl_id 
                             WHERE pt.pw_id = %s
                             LIMIT 1),
                            (SELECT p.id FROM product_product p 
                             JOIN product_template pt ON pt.id = p.product_tmpl_id 
                             WHERE pt.pw_default_product = TRUE
                             LIMIT 1)
                        ) AS product_id,
                        %s, %s, COALESCE(pt.name->>'en_US', 'Default Product'), COALESCE(pt.uom_id, 1), %s, %s, %s, %s, 'make_to_stock', %s
                    FROM product_template pt
                    LIMIT 1;
            """

            # Create a list of values to be inserted
            values = [
                (line['EVD_ID'], float(line['Quantity']), float(line['Quantity']), line['picking_id'].location_id.id,
                 line['picking_id'].location_dest_id.id, line['picking_id'].id, company.id,
                 line['picking_id'].date_done)
                for line in lines]

            # Execute the query using batch inserts
            self.env.cr.executemany(query, values)

            # Commit the transaction to save the changes
            self.env.cr.commit()

        except Exception as e:
            # Rollback in case of an error
            self.env.cr.rollback()
            _logger.error("Error inserting stock move: %s", e)

    def _generate_pw_id(self, order_type, date):
        return f'{order_type}{str(date).replace("-", "")}'

    @api.model
    def _get_picking_type_id(self, order_type, company):
        if order_type == 'robo':
            # From Robo to PW it has xlsx file in reference
            return company.robo_pw_operation_id
        elif order_type == 'offline':
            # Other orders
            return company.other_operation_id
        else:
            return company.online_operation_id

    def _action_log(self, desc, log_type):
        self.env['pw.log'].sudo().create({
            'date': fields.datetime.now(),
            'name': desc,
            'log_type': log_type,
        })
