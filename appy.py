import streamlit as st
import pdfplumber
import os, re, io, glob
from datetime import datetime
from docxtpl import DocxTemplate
import firebase_admin
from firebase_admin import credentials, firestore

# --- 1. إعدادات الألوان والتنسيق ---
Z_COPPER = "#BC846C"   # برونزي
Z_DARK = "#1B3022"     # أخضر غامق جداً
Z_LIGHT = "#F4F1EE"    # خلفية الصفحة

st.set_page_config(page_title="نظام الزمردة العقاري", layout="wide")

st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap');
    * {{ direction: RTL; text-align: right; font-family: 'Cairo', sans-serif; }}
    .stApp {{ background-color: {Z_LIGHT}; }}
    h1, h2, h3, p, span, label, .stMarkdown {{ color: {Z_DARK} !important; }}
    .main-card {{ background: white; padding: 25px; border-radius: 15px; border-right: 10px solid {Z_COPPER}; box-shadow: 0 4px 15px rgba(0,0,0,0.1); margin-top: 20px; }}
    .label-text {{ color: {Z_DARK}; font-weight: bold; font-size: 18px; }}
    .val-box {{ color: {Z_COPPER} !important; font-size: 24px; font-weight: 800; }}
    .stTabs [data-baseweb="tab"] p {{ color: {Z_DARK} !important; }}
    </style>
""", unsafe_allow_html=True)

# --- 2. إعداد السحابة (Firebase) - نسخة معالجة الأخطاء ---
@st.cache_resource
def init_firebase():
    try:
        if not firebase_admin._apps:
            if os.path.exists('firebase_key.json'):
                cred = credentials.Certificate('firebase_key.json')
                firebase_admin.initialize_app(cred)
            else:
                return None
        return firestore.client()
    except Exception as e:
        return None

db = init_firebase()

# --- 3. دوال البحث ---
def find_any_pdf():
    files = glob.glob("*.pdf")
    return files[0] if files else None

def get_unit_data(target_id):
    pdf_path = find_any_pdf()
    if not pdf_path: return None
    target_id = str(target_id).strip()
    try:
        with pdfplumber.open(pdf_path) as p:
            for page in p.pages:
                table = page.extract_table()
                if table:
                    for r in table[1:]:
                        if r and r[0] and str(r[0]).strip() == target_id:
                            price_str = "".join(re.findall(r'\d+', str(r[6]))) if len(r) > 6 else "0"
                            return {
                                'id': r[0], 'blk': r[1], 'area': r[4],
                                'price': float(price_str) if price_str else 0.0,
                                'status': 'متاح'
                            }
    except: return None
    return None

def format_money(amount):
    return "{:,.2f}".format(amount)

# --- 4. واجهة المستخدم ---
st.markdown(f"<h1 style='text-align:center;'>🏛️ بوابة مبيعات مشروع الزمردة</h1>", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["💎 المبيعات", "⚙️ تحديث السحابة"])

with tab1:
    search_id = st.text_input("🔍 ادخل رقم القطعة للبحث:")
    if search_id:
        res = get_unit_data(search_id)
        
        # محاولة جلب الحالة من السحابة إذا كانت متصلة
        if res and db:
            try:
                doc = db.collection('units').document(str(search_id)).get(timeout=5)
                if doc.exists:
                    res['status'] = doc.to_dict().get('status', 'متاح')
            except: pass

        if res:
            st.markdown(f"""
            <div class="main-card">
                <h2 style="margin-bottom:20px;">تفاصيل القطعة رقم {res['id']}</h2>
                <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px;">
                    <div><span class="label-text">رقم البلك:</span><br><span class="val-box">{res['blk']}</span></div>
                    <div><span class="label-text">المساحة:</span><br><span class="val-box">{res['area']} م²</span></div>
                    <div><span class="label-text">السعر الأساسي:</span><br><span class="val-box">{format_money(res['price'])} ريال</span></div>
                </div>
                <div style="margin-top:20px; border-top:1px solid #eee; padding-top:10px;">
                    <span class="label-text">الحالة الحالية:</span> <b style="color:{Z_COPPER}; font-size:20px;">{res['status']}</b>
                </div>
            </div>
            """, unsafe_allow_html=True)

            if res['status'] == 'متاح':
                st.write("---")
                col_c1, col_c2 = st.columns(2)
                with col_c1: cust_name = st.text_input("👤 اسم العميل:")
                with col_c2: discount_pct = st.number_input("📉 نسبة الخصم (%):", 0.0, 100.0, 0.0)

                final_p = res['price'] * (1 - discount_pct/100)
                total_w_fees = final_p + 2000
                
                st.info(f"الصافي: {format_money(final_p)} ريال | الإجمالي مع السعي: {format_money(total_w_fees)} ريال")

                if cust_name:
                    if st.button("📄 إصدار عرض السعر"):
                        template_path = "projecttemplate.docx"
                        if os.path.exists(template_path):
                            doc = DocxTemplate(template_path)
                            doc.render({
                                'date': datetime.now().strftime("%Y/%m/%d"),
                                'name': cust_name, 'id': res['id'], 'blk': res['blk'],
                                'area': res['area'], 'price': format_money(final_p),
                                'fees': "2,000.00", 'total': format_money(total_w_fees),
                                'desc': f"القطعة {res['id']} بلك {res['blk']} بمساحة {res['area']}"
                            })
                            out = io.BytesIO()
                            doc.save(out)
                            st.download_button("📥 تحميل عرض السعر", out.getvalue(), f"عرض_{cust_name}.docx")
            else:
                st.warning("⚠️ هذه القطعة محجوزة أو مباعة، لا يمكن إصدار عرض سعر لها.")
        else:
            st.error("❌ لم يتم العثور على القطعة في ملف الـ PDF.")

with tab2:
    st.subheader("إدارة حالة الوحدات")
    if db:
        u_id = st.text_input("رقم القطعة لتعديلها:")
        new_status = st.selectbox("اختر الحالة:", ["متاح", "محجوز", "مباع"])
        if st.button("تحديث السحابة الآن"):
            try:
                db.collection('units').document(str(u_id)).set({'status': new_status}, merge=True)
                st.success(f"✅ تم تحديث القطعة {u_id} بنجاح!")
            except Exception as e:
                st.error(f"فشل التحديث: {e}")
    else:
        st.error("السحابة غير متصلة. تأكد من ملف firebase_key.json.")
