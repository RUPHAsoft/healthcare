# -*- coding: utf-8 -*-
# Copyright (c) 2015, ESS LLP and contributors
# For license information, please see license.txt
from frappe import cint
from frappe.model.document import Document
from ruphasoft_hmis.insurance.custom.service_docs_helper import remove_item_sales_invoice


class LabPrescription(Document):
    pass

def create_lab_test(encounter, method=None):
    prescriptions = encounter.get("lab_test_prescription")
    if len(prescriptions) > 0:
        for prescription in prescriptions:
            if frappe.db.exists("Lab Test", {"prescription": prescription.get('name')}):
                update_lab_test(prescription, encounter)
                continue

            insert_new_lab_test(encounter, prescription)


def insert_new_lab_test(encounter, prescription):
    lab_test = frappe.new_doc("Lab Test")
    lab_test.template = prescription.get("lab_test_code")
    lab_test.lab_test_name = prescription.get("lab_test_name")
    lab_test.company = encounter.get('company')
    lab_test.patient = encounter.get('patient')
    lab_test.patient_name = encounter.get('patient_name')
    lab_test.prescription = prescription.get('name')
    appointment = encounter.get("appointment")
    lab_test.custom_appointment = appointment
    lab_test.patient_sex = encounter.get("patient_sex")
    lab_test.patient_age = encounter.get("patient_age")
    service_unit = frappe.get_cached_value("Patient Appointment", appointment, "service_unit", )
    lab_test.service_unit = service_unit
    lab_test.practitioner = encounter.practitioner
    lab_test.practitioner_name = encounter.practitioner_name
    lab_test.requesting_department = encounter.medical_department
    lab_test.insert(ignore_mandatory=True, ignore_permissions=True, ignore_links=True)


def update_lab_test(prescription, encounter):
    lab_test = frappe.db.get_value("Lab Test", {"prescription": prescription.get("name")}, ["name", "docstatus"],
                                   as_dict=True)

    if cint(lab_test.docstatus) == 1:
        frappe.throw("Lab Test already completed and invoiced")

    lab_test = frappe.get_doc("Lab Test", lab_test.name)

    if str(lab_test.get('template')) != str(prescription.get("lab_test_code")):
        lab_test.status = "Rejected"

        lab_test.flags.ignore_permissions = True
        lab_test.save()
        remove_item_sales_invoice(lab_test)

        insert_new_lab_test(encounter, prescription)


@frappe.whitelist()
def remove_prescription(lab_prescription, encounter):
    if frappe.db.exists("Lab Prescription", {"name": lab_prescription, "parent": encounter}) is None:
        return

    if frappe.db.exists("Lab Test", {"prescription": lab_prescription}) is None:
        return

    status = frappe.db.get_value("Lab Test", filters={"prescription": lab_prescription}, fieldname="status")

    if status not in ["Completed"]:
        frappe.db.delete("Lab Test", {"prescription": lab_prescription})


def validate_prescription_removal(encounter, method=None):
    old_encounter = encounter.get_doc_before_save()

    prescriptions_old = old_encounter.get("lab_test_prescription")

    new_prescriptions_list = encounter.get('lab_test_prescription')

    removed_prescriptions = []

    for prescription in prescriptions_old:
        if prescription not in new_prescriptions_list:
            removed_prescriptions.append(prescription)

    if len(removed_prescriptions) > 0:
        for prescription in removed_prescriptions:
            results = True
            lab_test_name = prescription.get('linked_lab_test', None)

            if lab_test_name is None:
                lab_test_name = frappe.db.get_value("Lab Test", {"prescription": prescription.get('name')}, "name")

            lab_test = frappe.get_cached_doc("Lab Test", lab_test_name)

            if lab_test.get('normal_test_items', None) or lab_test.get('descriptive_test_items', None):
                frappe.throw("Prescription has resulted Lab test")
