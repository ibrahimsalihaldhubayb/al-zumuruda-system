import streamlit as st
import pdfplumber
import os, re, io, glob
from datetime import datetime
from docxtpl import DocxTemplate

# --- 1. دوال البحث المتقدمة ---
def find_any_pdf():
    files = glob.glob("*.pdf")
    return files[0] if files else None

def get_data_turbo(target_id):
    pdf_path = find_any_pdf()
    if not pdf_path: return None
    
    target_id = str(target_id).strip()
    try:
        with pdfplumber.open(pdf_path) as p:
            for page in p.pages:
                text = page.extract_text()
                if text:
                    # تقسيم النص إلى أسطر والبحث عن السطر الذي يحتوي رقم القطعة
                    lines = text.split('\n')
                    for line in lines:
                        parts = line.split()
                        # إذا بدأ السطر برقم القطعة أو احتواه بشكل واضح
                        if parts and parts[0] == target_id:
                            # محاولة استخراج المساحة والسعر بناءً على ترتيب الأرقام في السطر
                            # نفترض أن المساحة هي الرقم الثالث والسعر هو الأخير تقريباً
                            nums = re.findall(r'[\d,.]+', line)
                            if len(nums) >= 4:
                                return {
                                    'id': nums[0],
                                    'blk': nums[1],
                                    'area': nums[4] if len(nums) > 4 else nums[2],
                                    'price': float(nums[-1].replace(',', '')) if nums[-1] else 0.0,
                                    'status': 'متاح'
                                }
                
                # محاولة ثانية عبر الجداول إذا فشل النص
                table = page.extract_table()
                if table:
                    for r in table:
                        if r and r[0] and str(r[0]).strip() == target_id:
                            p_val = "".join(re.findall(r'\d+', str(r[6]))) if len(r) > 6 else "0"
                            return {
                                'id': r[0], 'blk': r[1], 'area': r[4],
                                'price': float(p_val) if p_val else 0.0, 'status': 'متاح'
                            }
    except: return None
    return None

# --- 2. واجهة البرنامج (بسيطة وسريعة) ---
st.set_page_config(page_title="نظام الزمردة", layout="centered")
st.title("🏛️ بوابة مبيعات الزمردة")

# عرض اسم الملف المكتشف للتأكد
pdf_file = find_any_pdf()
if pdf_file:
    st.info(f"📁 يتم البحث الآن في ملف: {pdf_file}")
else:
    st.error("❌ لم يتم العثور على ملف PDF! ارفع الملف الآن.")

search_id = st.text_input("🔍 ادخل رقم القطعة (مثلاً: 1):")

if search_id:
    with st.spinner('جاري استخراج البيانات...'):
        res = get_data_turbo(search_id)
        
        if res:
            st.success("✅ تم العثور على البيانات")
            col1, col2, col3 = st.columns(3)
            col1.metric("رقم البلك", res['blk'])
            col2.metric("المساحة", f"{res['area']} م²")
            col3.metric("السعر", f"{res['price']:,} ريال")
            
            c_name = st.text_input("👤 اسم العميل لإصدار العرض:")
            if c_name:
                template_path = "projecttemplate.docx"
                if os.path.exists(template_path):
                    doc = DocxTemplate(template_path)
                    doc.render({'name': c_name, 'id': res['id'], 'blk': res['blk'], 'area': res['area'], 'price': f"{res['price']:,}"})
                    out_io = io.BytesIO()
                    doc.save(out_io)
                    st.download_button(f"📥 تحميل عرض {c_name}", data=out_io.getvalue(), file_name=f"عرض_{c_name}.docx")
        else:
            st.warning(f"لم يتم العثور على رقم {search_id} في الملف. تأكد من الرقم.")

