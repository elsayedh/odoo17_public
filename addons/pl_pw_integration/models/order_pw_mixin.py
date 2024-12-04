from odoo import fields, models, api, _
import requests
from datetime import timedelta
import json
from collections import defaultdict
import logging

from odoo.addons.base.models.ir_model import select_en
from odoo.release import serie

_logger = logging.getLogger(__name__)


class OrderPWMixin(models.AbstractModel):
    _name = 'order.pw.mixin'
    _description = 'Order PW Mixin'

    pw_id = fields.Char(string='PW ID')

    @api.model
    def fetch_orders(self, batch_size=5000, retry_limit=3, **kwargs):
        companies = self.env['res.company'].search([('pw_access_token', '!=', False)])
        if not companies:
            _logger.info(_('No companies found with a valid access token.'))
            return

        # Default date range
        date_from = fields.Date.from_string(kwargs.get('date')) if kwargs.get(
            'date') else fields.Date.today() - timedelta(days=1)
        date_to = fields.Date.from_string(kwargs.get('date_to')) if kwargs.get('date_to') else date_from

        for company in companies:

            order_vals = []

            while date_from <= date_to:
                fetch_date = date_from

                url = self.env['ir.config_parameter'].sudo().get_param(kwargs['endpoint_param_key'])
                payload = self._prepare_payload(fetch_date, kwargs['order_type'], kwargs.get('json_payload'))
                headers = self._prepare_headers(company, kwargs.get('json_payload'))

                # Fetch transactions in batch with retry mechanism
                orders = self._fetch_transactions_with_retry(url, headers, payload, kwargs['order_type'],
                                                             kwargs['transaction_list_name'], fetch_date,
                                                             retry_limit)
                if not orders:
                    date_from += timedelta(days=1)
                    continue

                # Prepare order for batch processing
                order_vals += self._prepare_order(orders, fetch_date, company)

                date_from += timedelta(days=1)

            if order_vals:
                self._process_orders_in_batches(order_vals, company, batch_size, kwargs['order_type'],
                                                kwargs.get('date') or date_from, kwargs.get('date_to') or date_to)

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
            while temp_index < total_orders and batch[-1]['order_id'].id == order_vals[temp_index]['order_id'].id:
                batch.append(order_vals[temp_index])  # Add the next item with the same order_id to the batch
                temp_index += 1  # Move the index forward

            # Update total posted orders count
            total_posted_orders += len(batch)

            try:
                # Insert orders in batches
                self._insert_sale_order_lines(batch, company)


                order_ids = self
                for val in batch:
                    order_ids |= val['order_id']


                # Recompute and post the orders
                self._recompute_fields(order_ids)

                order_ids.sudo()._sale_order_confirmation(skip_check_invoicing_policy=True)

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

    def _prepare_order(self, orders, date, company):

        if "0" in orders:
            orders.pop("0")

        order_vals = []

        for pw_id, order_data in orders.items():
            # Check if order is existing
            query = """
                    SELECT sale.id
                    FROM sale_order sale
                    WHERE sale.pw_id = %s 
                    AND sale.state != 'cancel'
                """

            self.env.cr.execute(query, (pw_id,))
            result = self.env.cr.fetchall()

            if result:
                _logger.error(_('Order with same ID: %s already exists'), pw_id)
                continue

            # order_id = self._insert_order(
            #     self._get_partner_by_pos_id(order_data['Customer']['Vat_no'],
            #                                 order_data['Customer']['POS_ID']),
            #     date, pw_id, company
            # )

            order_id = self.env['sale.order'].sudo().create({
                'partner_id': self._get_partner_by_pos_id(order_data['Customer']['POS_ID'],
                                                          order_data['Customer']['Vat_no']),
                'date_order': date,
                'pw_id': pw_id,
                'company_id': company.id,
            })

            order_vals += list(map(lambda d: {**d, 'order_id': order_id}, order_data['Products']))

            _logger.info(_('Order %s was prepared' % pw_id))

        return order_vals

    def _get_partner_by_pos_id(self, pos_id, vat):
        if not pos_id:
            return False

        pos_id = pos_id.upper()  # Convert PW code to capital case

        # SQL query to fetch the partner ID by pos_id
        query = """
               SELECT id
               FROM res_partner
               WHERE pw_pos_id = %s
               LIMIT 1;
           """
        # Execute the SQL query with pos_id as a parameter
        self.env.cr.execute(query, (pos_id,))

        # Fetch one record (since we use LIMIT 1)
        result = self.env.cr.fetchone()

        if result:
            return result[0]  # The ID is the first column in the result

        return self._create_unknown_customer(vat, pos_id)  # Create unknown customer if it is not exist

    def _create_unknown_customer(self, vat, pos):
        return self.env['res.partner'].sudo().create({
            'name': _('Unknown Customer'),
            'customer_rank': 1,
            'vat': vat,
            'pw_pos_id': pos
        }).id

    def _insert_order(self, partner_id, date_order, pw_id, company):

        query = '''
            INSERT INTO sale_order (name, partner_id, partner_invoice_id, partner_shipping_id, date_order, pw_id, company_id) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id;
        '''

        try:
            self.env.cr.execute(query, (
                _('New'),
                partner_id,
                partner_id,
                partner_id,
                date_order,
                pw_id,
                company.id))

            order_id = self.env.cr.fetchone()[0]

            # Commit the transaction to save the changes
            self.env.cr.commit()

            return order_id

        except Exception as e:
            # Rollback in case of an error
            self.env.cr.rollback()
            _logger.error("Error create order: %s", e)

    def _insert_sale_order_lines(self, lines, company):
        """
            Insert sale order lines into the database in bulk.

            :param lines: List of dictionaries containing line items data
            :type lines: list
            :param order_id: Sale order ID
            :type order_id: int

            :return: True if insertion is successful
            :rtype: bool
        """

        if not lines:
            return

        # Prepare the base SQL query
        query = """
                    INSERT INTO sale_order_line (product_id, product_uom_qty, price_unit, name, order_id, customer_lead, product_uom, company_id)
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
                        %s, %s, COALESCE(pt.name->>'en_US', 'Default Product'), %s, 0.0, COALESCE(pt.uom_id, 1), %s
                    FROM product_template pt
                    LIMIT 1;
        """

        # Create a list of values to be inserted
        values = [(item['ProductsID'], float(item['quantity']), float(item['price']), item['order_id'].id, company.id)
                  for item in lines]

        # Use a transaction to commit in bulk
        try:
            # Execute the query using batch inserts
            self.env.cr.executemany(query, values)

            # Commit the transaction to save the changes
            self.env.cr.commit()

        except Exception as e:
            # Rollback in case of an error
            self.env.cr.rollback()
            _logger.error("Error inserting sale order lines: %s", e)

        return True

    def _recompute_fields(self, order_ids):
        # Recompute totals
        self.env.add_to_compute(order_ids.order_line._fields['tax_id'], order_ids.order_line)
        self.env.add_to_compute(order_ids.order_line._fields['price_subtotal'], order_ids.order_line)
        self.env.add_to_compute(order_ids.order_line._fields['price_tax'], order_ids.order_line)
        self.env.add_to_compute(order_ids.order_line._fields['price_total'], order_ids.order_line)

        self.env.add_to_compute(order_ids._fields['amount_untaxed'], order_ids)
        self.env.add_to_compute(order_ids._fields['amount_tax'], order_ids)
        self.env.add_to_compute(order_ids._fields['amount_total'], order_ids)

    def _action_log(self, desc, log_type, pw_order_id=False):
        self.env['pw.log'].sudo().create({
            'date': fields.datetime.now(),
            'name': desc,
            'pw_id': pw_order_id,
            'log_type': log_type,
        })
