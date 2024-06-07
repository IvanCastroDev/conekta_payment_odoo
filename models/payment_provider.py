
import logging

from odoo import models, fields, api
_logger = logging.getLogger(__name__)

class PaymentAcquirer(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('conekta', 'Conekta'), ('conekta_oxxo', 'Conekta oxxo'), ('conekta_spei', 'Conekta SPEI')],
        ondelete={'conekta': 'set default', 'conekta_oxxo': 'set default', 'conekta_spei': 'set default'})
    conekta_secret_key = fields.Char(string="Conekta Secret Key")
    conekta_publishable_key = fields.Char(string="Conekta Public Key")
    conekta_secret_key_test = fields.Char(string="Conekta Secret Key Test")
    conekta_publishable_key_test = fields.Char(string="Conekta Public Key Test")

    @api.model
    def _get_compatible_acquirers(self, *args, currency_id=None, **kwargs):
        """ Override of payment to unlist acquirers for unsupported currencies. """
        acquirers = super()._get_compatible_acquirers(*args, currency_id=currency_id, **kwargs)

        currency = self.env['res.currency'].browse(currency_id).exists()
        if currency and currency.name not in ['MXN', 'USD']:
            acquirers = acquirers.filtered(
                lambda a: a.code not in ['conekta', 'conekta_oxxo', 'conekta_spei']
            )
        return acquirers

    def _get_default_payment_method_id(self, code):
        self.ensure_one()
        if self.code == 'conekta':
            return self.env.ref('payment_conekta_oxoo.payment_method_conekta').id
        if self.code == 'conekta_oxxo':
            return self.env.ref('payment_conekta_oxoo.payment_method_conekta_oxxo').id
        if self.code == 'conekta_spei':
            return self.env.ref('payment_conekta_oxoo.payment_method_conekta_spei').id
        return super()._get_default_payment_method_id(code)

    @api.model
    def conekta_s2s_form_process(self, data):
        payment_token = self.env['payment.token'].sudo().create({
            'provider_id': int(data['provider_id']),
            'partner_id': int(data['partner_id']),
            'conekta_token': data.get('conekta_token'),
            'provider_ref': data.get('conekta_token'),
            'payment_details': 'XXXXXXXXXXXX%s - %s' % (data['cc_number'][-4:], data['cc_holder_name']),
        })
        return payment_token
    
    