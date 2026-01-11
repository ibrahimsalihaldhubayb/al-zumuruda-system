import streamlit as st
import pdfplumber
import os, re, io, glob
from datetime import datetime
from docxtpl import DocxTemplate
import firebase_admin
from firebase_admin import credentials, firestore

# --- 1. إعداد Firebase (مع حماية ضد أعطال الاتصال) ---
@st.cache_resource
def init_firebase():
    if not firebase_admin._apps:
        try:
            # التحقق من وجود الملف وصلاحيته
            if os.path.exists('firebase_key.json'):
                cred = credentials.Certificate('firebase_key.json')
                firebase_admin.initialize_app(cred)
                return firestore.client()
        except Exception as e:
            # إذا فشل الاتصال لا توقف البرنامج، فقط سجل الخطأ
            print(f"Firebase connection failed: {e}")
            return None
    else:
        try: return firestore.client()
        except: return None
    return None

db = init_firebase()

# --- 2. البحث التلقائي عن ملف الـ PDF ---
def find_any_pdf():
    files = glob.glob("*.pdf")
    return files[0] if files else None

# --- 3. دالة البحث في الـ PDF ---
def get_data_from_pdf(target_id):
    pdf_path = find_any_pdf()
    if not pdf_path: return None
    try:
        with pdfplumber.open(pdf_path) as p:
            for page in p.pages:
                table = page.extract_table()
                if table:
                    for r in table[1:]:
                        if r and len(r) > 0 and r[0]:
                            if str(r[0]).strip() == str(target_id).strip():
                                price_val = "".join(re.findall(r'\d+', str(r[6]))) if len(r) > 6 and r[6] else "0"
                                return {
                                    'id': r[0],
                                    'blk': r[1] if len(r) > 1 else "-",
                                    'area': r[4] if len(r) > 4 else "-",
                                    'price': float(price_val) if price_val else 0.0,
                                    'status': 'متاح'
                                }
    except: return None
    return None

def format_money_en(amount):
    return "{:,.2f}".format(amount)

# --- واجهة البرنامج ---
st.set_page_config(page_title="نظام الزمردة", layout="wide")
st.markdown("<h1 style='text-align:center;'>🏛️ نظام مبيعات الزمردة</h1>", unsafe_allow_html=True)

search_id = st.text_input("🔍 ادخل رقم القطعة للبحث:")

if search_id:
    res = None
    
    # محاولة البحث في السحابة (فقط إذا كانت تعمل)
    if db:
        try:
            doc_ref = db.collection('units').document(str(search_id)).get(timeout=5)
            if doc_ref.exists:
                res = doc_ref.to_dict()
        except:
            # إذا فشلت السحابة، ننتقل للـ PDF بصمت
            res = None

    # البحث في الـ PDF (المصدر الموثوق دائماً)
    if not res:
        res = get_data_from_pdf(search_id)

    if res:
        st.success(f"✅ تم العثور على القطعة رقم {res['id']}")
        st.markdown(f"**رقم البلك:** {res['blk']} | **المساحة:** {res['area']} م²")
        st.markdown(f"**السعر:** <span style='font-size:20px; color:#BC846C;'>{format_money_en(float(res['price']))} ريال</span>", unsafe_allow_html=True)
        
        c_name = st.text_input("👤 اسم العميل الموقر:")
        if c_name:
            # معالجة ملف الوورد
            template_path = "projecttemplate.docx"
            if os.path.exists(template_path):
                try:
                    doc = DocxTemplate(template_path)
                    context = {
                        'date': datetime.now().strftime("%Y/%m/%d"),
                        'name': c_name,
                        'id': res['id'], 'blk': res['blk'], 'area': res['area'],
                        'price': format_money_en(float(res['price'])),
                        'total': format_money_en(float(res['price']) + 2000),
                        'fees': "2,000.00"
                    }
                    doc.render(context)
                    out_io = io.BytesIO()
                    doc.save(out_io)
                    st.download_button(f"📥 تحميل عرض سعر {c_name}", data=out_io.getvalue(), file_name=f"عرض_{c_name}.docx")
                except Exception as e:
                    st.error(f"خطأ في إنشاء الوورد: {e}")
    else:
        st.error("❌ القطعة غير موجودة في الـ PDF أو السحابة.")

