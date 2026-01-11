import streamlit as st
import pdfplumber
import os, re, io, glob
from datetime import datetime
from docxtpl import DocxTemplate
import firebase_admin
from firebase_admin import credentials, firestore

# --- 1. إعداد Firebase ---
@st.cache_resource
def init_firebase():
    if not firebase_admin._apps:
        try:
            cred_path = 'firebase_key.json'
            if os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
                return firestore.client()
            return None
        except: return None
    else: return firestore.client()

db = init_firebase()

# --- 2. دالة استخراج السعر ---
def extract_price(price_val):
    if not price_val: return 0.0
    num = "".join(re.findall(r'\d+', str(price_val)))
    return float(num) if num else 0.0

def format_money_en(amount):
    return "{:,.2f}".format(amount).replace('٫', '.').replace('٬', ',')

# --- 3. محرك الوورد ---
def create_word_offer(data, cust_name, net_p):
    try:
        template_path = "Projecttemmplate.docx"
        if not os.path.exists(template_path):
            return None
        doc = DocxTemplate(template_path)
        office_fees = 2000.00 
        total_with_fees = net_p + office_fees
        context = {
            'date': datetime.now().strftime("%Y/%m/%d"),
            'name': str(cust_name),
            'id': str(data['id']),
            'blk': str(data['blk']),
            'area': str(data['area']),
            'price': str(format_money_en(net_p)), 
            'fees': str(format_money_en(office_fees)),
            'total': str(format_money_en(total_with_fees)),
            'desc': f"بلك: {data['blk']} - مساحة: {data['area']} م²"
        }
        doc.render(context)
        out_io = io.BytesIO()
        doc.save(out_io)
        return out_io.getvalue()
    except: return None

# --- الواجهة ---
st.set_page_config(page_title="نظام الزمردة", layout="wide")

# التحقق من وجود الملف
pdf_path = "الوحدات الشاغرة في مشروع الزمردة حتى تاريخ 28-12-2025.pdf"
if not os.path.exists(pdf_path):
    st.error(f"⚠️ تنبيه: ملف الـ PDF غير موجود في المستودع! تأكد من رفعه باسم: {pdf_path}")

search_id = st.text_input("🔍 ابحث عن رقم القطعة:")

if search_id:
    uid = str(search_id).strip()
    res = None
    
    # البحث في السحابة
    if db:
        doc_cloud = db.collection('units').document(uid).get()
        if doc_cloud.exists: res = doc_cloud.to_dict()
    
    # البحث في الـ PDF (مباشرة بدون كاش للتأكد)
    if not res and os.path.exists(pdf_path):
        with pdfplumber.open(pdf_path) as p:
            for page in p.pages:
                table = page.extract_table()
                if table:
                    for r in table[1:]:
                        if r and r[0] and str(r[0]).strip() == uid:
                            res = {
                                'id': r[0], 
                                'blk': r[1], 
                                'area': r[4], 
                                'price': extract_price(r[6]), 
                                'status': 'متاح'
                            }
                            break

    if res:
        st.success(f"تم العثور على القطعة رقم {res['id']}")
        st.write(f"البلك: {res['blk']} | المساحة: {res['area']} | السعر: {res['price']}")
        
        c_name = st.text_input("اسم العميل:")
        if c_name:
            word_file = create_word_offer(res, c_name, float(res['price']))
            if word_file:
                st.download_button("📥 تحميل العرض", data=word_file, file_name=f"عرض_{uid}.docx")
    else:
        st.warning("❌ لم يتم العثور على هذه القطعة. تأكد من الرقم.")
