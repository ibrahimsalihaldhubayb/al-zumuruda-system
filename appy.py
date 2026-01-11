import streamlit as st
import pdfplumber
import os, re, io, glob
from datetime import datetime
from docxtpl import DocxTemplate
import firebase_admin
from firebase_admin import credentials, firestore

# --- 1. إعدادات المظهر والسرعة ---
st.set_page_config(page_title="نظام الزمردة السريع", layout="wide")

@st.cache_resource
def init_firebase():
    try:
        if not firebase_admin._apps:
            if os.path.exists('firebase_key.json'):
                cred = credentials.Certificate('firebase_key.json')
                firebase_admin.initialize_app(cred)
        return firestore.client()
    except: return None

db = init_firebase()

# --- 2. محرك البحث فائق السرعة (يقرأ مرة واحدة فقط) ---
@st.cache_data(show_spinner="⚡ جاري شحن قاعدة البيانات لسرعة البحث...")
def get_all_units_cached():
    pdf_files = glob.glob("*.pdf")
    if not pdf_files: return {}
    
    inventory = {}
    try:
        with pdfplumber.open(pdf_files[0]) as p:
            for page in p.pages:
                table = page.extract_table()
                if table:
                    for r in table[1:]:
                        if r and len(r) > 6 and r[0]:
                            uid = str(r[0]).strip()
                            price_raw = "".join(re.findall(r'\d+', str(r[6])))
                            inventory[uid] = {
                                'id': uid,
                                'blk': r[1],
                                'area': r[4],
                                'price': float(price_raw) if price_raw else 0.0
                            }
    except Exception as e:
        print(f"Error loading PDF: {e}")
    return inventory

# تحميل البيانات في ذاكرة السيرفر فور تشغيل التطبيق
units_data = get_all_units_cached()

# --- 3. الواجهة الرسومية ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap');
    * { direction: RTL; text-align: right; font-family: 'Cairo', sans-serif; color: #1B3022; }
    .stApp { background-color: #F4F1EE; }
    .card { background: white; padding: 20px; border-radius: 12px; border-right: 8px solid #BC846C; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
    .price-tag { color: #BC846C; font-size: 24px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

st.title("🏛️ نظام مبيعات الزمردة (النسخة السريعة)")

# البحث اللحظي من الذاكرة
search_query = st.text_input("🔍 ادخل رقم القطعة (البحث الآن فوري):")

if search_query:
    uid = search_query.strip()
    if uid in units_data:
        unit = units_data[uid]
        
        # جلب الحالة من السحابة (اختياري)
        status = "متاح"
        if db:
            try:
                doc = db.collection('units').document(uid).get(timeout=1)
                if doc.exists: status = doc.to_dict().get('status', 'متاح')
            except: pass

        st.markdown(f"""
        <div class="card">
            <h3>القطعة رقم {unit['id']} - <span style="color:#BC846C">{status}</span></h3>
            <p>رقم البلك: <b>{unit['blk']}</b> | المساحة: <b>{unit['area']} م²</b></p>
            <p>السعر الأساسي: <span class="price-tag">{unit['price']:,.2f} ريال</span></p>
        </div>
        """, unsafe_allow_html=True)

        if status == "متاح":
            st.write("---")
            col1, col2 = st.columns(2)
            c_name = col1.text_input("👤 اسم العميل:")
            discount = col2.number_input("📉 نسبة الخصم %:", 0.0, 100.0, 0.0)
            
            final_p = unit['price'] * (1 - discount/100)
            total_final = final_p + 2000
            
            st.success(f"الصافي: {final_p:,.2f} ريال | الإجمالي مع السعي: {total_final:,.2f} ريال")
            
            if c_name and st.button("📄 توليد عرض السعر"):
                template = "projecttemplate.docx"
                if os.path.exists(template):
                    doc = DocxTemplate(template)
                    doc.render({
                        'date': datetime.now().strftime("%Y/%m/%d"),
                        'name': c_name, 'id': unit['id'], 'blk': unit['blk'],
                        'area': unit['area'], 'price': f"{final_p:,.2f}",
                        'fees': "2,000.00", 'total': f"{total_final:,.2f}",
                        'desc': f"القطعة {unit['id']} بلك {unit['blk']}"
                    })
                    output = io.BytesIO()
                    doc.save(output)
                    st.download_button(f"📥 تحميل العرض لـ {c_name}", output.getvalue(), f"عرض_{c_name}.docx")
    else:
        st.error("❌ الرقم غير موجود في ملف الوحدات.")
