# © 2009 Tech-Receptives Solutions Pvt. Ltd.
# © 2018 FactorLibre
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import logging
from odoo import _
from odoo.addons.component.core import Component
from odoo.addons.connector.components.mapper import mapping

_logger = logging.getLogger(__name__)


class CustomerBatchImporter(Component):
    """ Import the WooCommerce Partners.

    For every partner in the list, a delayed job is created.
    """

    _name = "woocommerce.partner.batch.importer"
    _inherit = "woocommerce.delayed.batch.importer"
    _apply_on = "woo.res.partner"

    def run(self, filters=None):
        """ Run the synchronization """
        from_date = filters.pop("from_date", None)
        to_date = filters.pop("to_date", None)
        record_ids = self.backend_adapter.search(
            filters, from_date=from_date, to_date=to_date
        )
        _logger.info("search for woo partners %s returned %s", filters, record_ids)
        for record_id in record_ids:
            self._import_record(record_id)


class CustomerImporter(Component):
    _name = "woocommerce.partner.importer"
    _inherit = "woocommerce.importer"
    _apply_on = "woo.res.partner"

    def run(self, external_id, force=False):
        res = super().run(external_id, force)
        binder = self.binder_for("woo.res.partner")
        shipping_binding = binder.to_internal(str(self.external_id) + "_shipping")
        map_shipping = self._map_data()
        if shipping_binding:
            record = self._update_data(map_shipping, shipping_data=True)
            if record['street']:
                self._update(shipping_binding, record)
        else:
            record = self._create_data(map_shipping, shipping_data=True)
            if record['street']:
                shipping_binding = self._create(record)
        if shipping_binding:
            self.binder.bind(str(self.external_id) + "_shipping", shipping_binding)
            self._after_import(shipping_binding)
        return res

    def _check_vat(self, vat_number, partner_country):
        vat_country, vat_number_ = self.env["res.partner"]._split_vat(vat_number)
        if not self.env["res.partner"].simple_vat_check(vat_country, vat_number_):
            # if fails, check with country code from country
            country_code = partner_country.code
            if country_code:
                if not self.env["res.partner"].simple_vat_check(
                    country_code.lower(), vat_number
                ):
                    return False
        return True

    def _after_import(self, binding):
        if binding.type != "delivery":
            vat_number = None
            record = self.woo_record
            if self.backend_record.partner_vat_field:
                for meta_field in record.get("meta_data"):
                    if meta_field["key"] == self.backend_record.partner_vat_field:
                        vat_number = meta_field["value"]

            if vat_number:
                vat_number = (
                    vat_number.replace(".", "").replace(" ", "").replace("-", "")
                )
                if self._check_vat(vat_number, binding.odoo_id.country_id):
                    binding.write({"vat": vat_number, "woo_vatnumber": vat_number})
                else:
                    binding.write({"woo_vatnumber": vat_number})
                    msg = _("Please, check the VAT number: %s") % vat_number
                    self.backend_record.activity_schedule('mail.mail_activity_data_warning', summary=_('VAT number error'), note=msg)


class CustomerImportMapper(Component):
    _name = "woocommerce.partner.import.mapper"
    _inherit = "woocommerce.import.mapper"
    _apply_on = "woo.res.partner"

    direct = [("email", "email")]

    @mapping
    def name(self, record):
        if not self.options.get("shipping_data") and record['billing'].get('company'):
            return {'name': record['billing'].get('company')}
        if record.get("first_name") or record.get("last_name"):
            return {"name": record["first_name"] + " " + record["last_name"]}
        else:
            return {"name": record.get("username")}

    @mapping
    def is_company(self, record):
        if not self.options.get("shipping_data") and record['billing'].get('company'):
            return {'is_company': True}

    @mapping
    def city(self, record):
        address_type = self.options.get("shipping_data") and "shipping" or "billing"
        if record.get(address_type):
            rec = record[address_type]
            return {"city": rec["city"] or None}

    @mapping
    def zip(self, record):
        address_type = self.options.get("shipping_data") and "shipping" or "billing"
        if record.get(address_type):
            rec = record[address_type]
            return {"zip": rec["postcode"] or None}

    @mapping
    def address(self, record):
        address_type = self.options.get("shipping_data") and "shipping" or "billing"
        if record.get(address_type):
            rec = record[address_type]
            return {"street": rec["address_1"] or None}

    @mapping
    def address_2(self, record):
        address_type = self.options.get("shipping_data") and "shipping" or "billing"
        if record.get(address_type):
            rec = record[address_type]
            return {"street2": rec["address_2"] or None}

    @mapping
    def country(self, record):
        address_type = self.options.get("shipping_data") and "shipping" or "billing"
        if record.get(address_type):
            rec = record[address_type]
            if rec["country"]:
                country_id = self.env["res.country"].search(
                    [("code", "=", rec["country"])]
                )
                country_id = country_id.id
            else:
                country_id = False
            return {"country_id": country_id}

    @mapping
    def state(self, record):
        address_type = self.options.get("shipping_data") and "shipping" or "billing"
        if record.get(address_type):
            rec = record[address_type]
            if rec["state"] and rec["country"]:
                country = self.env["res.country"].search(
                    [("code", "=", rec["country"])]
                )
                state = self.env["res.country.state"].search(
                    [("code", "=", rec["state"]), ("country_id", "=", country.id)]
                )
                return {"state_id": state.id}

    @mapping
    def type(self, record):
        if self.options.get("shipping_data"):
            return {"type": "delivery"}

    @mapping
    def parent_id(self, record):
        if self.options.get("shipping_data"):
            binder = self.binder_for("woo.res.partner")
            parent = binder.to_internal(record["id"], unwrap=True)
            return {"parent_id": parent.id}

    @mapping
    def backend_id(self, record):
        return {"backend_id": self.backend_record.id}

    @mapping
    def phone(self, record):
        return {"phone": record.get("billing", {}).get("phone")}
