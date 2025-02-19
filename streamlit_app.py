import copy
import cv2
import datetime
import os
import numpy as np
import pandas as pd
import streamlit as st
import altair as alt
from vega_datasets import data
from PIL import Image
from tensorflow.keras.applications.mobilenet_v2 import preprocess_input
from tensorflow.keras.preprocessing.image import img_to_array
from tensorflow.keras.models import load_model


@st.cache(persist=True)
def load_data(path):
    data=pd.read_csv(path)
    return data

def show_visualization():

    #load in data
    fb_mask_original=load_data("fb_mask.csv")
    fb_sympton_original=load_data("fb_sympton.csv")
    fb_sympton=copy.deepcopy(fb_sympton_original)
    fb_mask=copy.deepcopy(fb_mask_original)
    fb_mask['time_value']= pd.to_datetime(fb_mask['time_value'], format='%Y/%m/%d')
    fb_sympton['time_value']= pd.to_datetime(fb_sympton['time_value'], format='%Y/%m/%d')
    fb_mask.rename(columns={'value':'mask_percentage'}, inplace=True)
    fb_sympton.rename(columns={'value':'sympton_percentage'}, inplace=True)

    fb_all=fb_mask.merge(fb_sympton, on=['time_value','geo_value'])
    fb_all=fb_all[['geo_value','time_value','mask_percentage','sympton_percentage']]
    fb_all = fb_all[fb_all['time_value']>'2020-09-08']

    states=fb_all.geo_value.str.upper().unique()

    #first plot: correlation between wearing mask and having symptons
    st.title("Face Mask Analysis During Covid-19 Pandemic")
    st.write("In the face of the COVID-19 pandemic, it has been shown that wearing masks is an effective way to prevent the spread of the disease. CDC calls people to wear masks, and masks are required in public transportation and restaurants. Our app aims to demonstrate the effectiveness of wearing masks, and show how wearing masks can increase safety level in real world scenarios.")
           
    st.header("Part 1: Effectiveness of Face Masks")
    st.write("The dataset we are using comes from the survey conducted by Delphi Group and Facebook. [Link](https://delphi.cmu.edu/covidcast/?sensor=doctor-visits-smoothed_adj_cli&level=county&date=20201202&signalType=value&encoding=color&mode=export®ion=42003)")
    st.subheader("Correlation between wearing masks and having symptoms.")
    
    st.sidebar.title('Visualization Options:')
    state_choice = st.sidebar.multiselect(
        "Which states are you interested in? Please choose more than one state",
        states.tolist(), default=states.tolist()
    )

    date_range = st.sidebar.date_input("Which range of date are you interested in? Choose between %s and %s"% (min(fb_all['time_value']).strftime('%Y/%m/%d'),  max(fb_all['time_value']).strftime('%Y/%m/%d')), [min(fb_all['time_value']), max(fb_all['time_value'])])

    fb_temp = fb_all[fb_all['geo_value'].str.upper().isin(state_choice)]

    if len(date_range)==2:
        fb_selected = fb_temp[(fb_temp['time_value']>=pd.to_datetime(date_range[0])) & (fb_temp['time_value']<=pd.to_datetime(date_range[1]))]
    else:
        fb_selected = fb_temp[(fb_temp['time_value']>=pd.to_datetime(date_range[0]))]



    fb_selected.columns = ['state', 'time_value', 'mask percentage(%)', 'symptom percentage(%)']

    fb_selected=fb_selected.groupby(['state']).mean().reset_index()

    fb_selected['state'] = fb_selected['state'].str.upper() 

    fb_selected['mask percentage(%)']=round(fb_selected['mask percentage(%)'],2)
    fb_selected['symptom percentage(%)']=round(fb_selected['symptom percentage(%)'],2)

    scatter_chart = alt.Chart(fb_selected).mark_circle().encode(
        x=alt.X('mask percentage(%)', scale=alt.Scale(zero=False), axis=alt.Axis(title='percentage of wearing masks')), 
        y=alt.Y('symptom percentage(%)', scale=alt.Scale(zero=False), axis=alt.Axis(title='percentage of having covid symptoms')),
        tooltip=['state', 'mask percentage(%)', 'symptom percentage(%)']
    )

    scatter_chart.interactive() + scatter_chart.transform_regression('mask percentage(%)', 'symptom percentage(%)').mark_line()
    
    
    st.subheader("Geographic representation of wearing masks and having symptoms.")
    map_data = fb_all[fb_all['time_value']==pd.to_datetime(date_range[0])].copy()
    ids = [2,1,5,4,6,8,9,11,10,12,13,15,19,16,17,18,20,21,22,25,24,23,26,27,29,28,30,37,38,31,33,34,35,32,
           36,39,40,41,42,44,45,46,47,48,49,51,50,53,55,54,56] 
    map_data['id'] = ids
    map_data['unmasked_percentage'] = 100-map_data['mask_percentage']

    states = alt.topo_feature(data.us_10m.url, 'states')
    variable_list = ['unmasked_percentage','sympton_percentage']

    chart = alt.Chart(states).mark_geoshape().encode(
        alt.Color(alt.repeat('row'), type='quantitative')
    ).transform_lookup(
        lookup='id',
        from_=alt.LookupData(map_data, 'id', variable_list)
    ).properties(
        width=500,
        height=300
    ).project(
        type='albersUsa'
    ).repeat(
        row=variable_list
    ).resolve_scale(
        color='independent'
    )

    st.write(chart)

    st.write("As demonstrated in previous diagrams, wearing masks can mitigate the spread of the COVID-19 virus. As more and more states are reopening, it’s critical for us to understand the importance of masks, and be able to evaluate the safety level of everyday scenarios. Only then can we make wise decisions to protect ourselves and help prevent the spread of the virus.")


def mask_detection(image, conf=0.5):

    FACE_MODEL_PATH = "./model/face_detector.caffemodel"
    FACE_PROTO_PATH = "./model/deploy.prototxt"
    MASK_MODEL_PATH =  "./model/mask_detector.model"
    IMG_RESIZE = 300

    # record output values
    faces = []
    height, width = image.shape[:2]

    # load models
    model = load_model(MASK_MODEL_PATH)
    net = cv2.dnn.readNet(FACE_PROTO_PATH, FACE_MODEL_PATH)
    net.setInput(cv2.dnn.blobFromImage(image, size=(IMG_RESIZE, IMG_RESIZE)))

    detections = net.forward()

    cur, low, high = 0, 0, 0
    for i in range(detections.shape[2]):

        # filter out non-faces
        if detections[0, 0, i, 2] > conf:

            cur += 1

            # compute face bounding box
            x1, y1, x2, y2 = detections[0, 0, i, 3:7]
            x1, y1, x2, y2 = max(0, int(x1*width)), max(0, int(y1*height)), min(width-1, int(x2*width)), min(height-1, int(y2*height))

            # transform face image for mask detector
            face = cv2.cvtColor(image[y1:y2, x1:x2], cv2.COLOR_BGR2RGB)
            face = cv2.resize(face, (224, 224))
            face = np.expand_dims(preprocess_input(img_to_array(face)), axis=0)

            # mask detection for faces
            mask, noMask = model.predict(face)[0]
            prob = max(mask, noMask)*100
            label, color = "No Mask", (0, 0, 255) # red
            if mask > noMask: 
                label, color = "Mask", (0, 255, 0) # green

            # store face info for scoring step
            face_info = {}
            face_info["cord"] = (x1, y1, x2, y2)
            face_info["prob"] = prob * (2*(mask > noMask)-1)
            faces.append(face_info)

            # draw result on image
            text = "%s: %.1f%%"%(label, prob)
            font_scale, font, thickness = (abs(x1-x2))/(160), cv2.FONT_HERSHEY_DUPLEX, 1
            text_size, _ = cv2.getTextSize(text, font, font_scale, thickness)
            text_location = ((x1+x2)//2 - text_size[0]//2, y2 + int(text_size[1] * 1.5))
            cv2.putText(image, text, text_location, font, font_scale, color, thickness)
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)

        if detections[0, 0, i, 2] > 0.25:
            low += 1
        if detections[0, 0, i, 2] > 0.75:
            high += 1

    return image, faces, (cur, low, high)

def process_mask_image():
    
    IMAGE_PATH = "./images/"

    st.set_option('deprecation.showfileUploaderEncoding', False)

    st.header("Part 2: Real World Implications")
    st.write("Given an image representing a real world scenario, we are able to evaluate the COVID-19 safety level based on mask-wearing rates and the distances between people.")
    st.subheader("Face Mask Detection")
    st.sidebar.title('Mask Detection Options:')

    select_image = None
    upload_image = None
    
    # select sample images
    sample_images = sorted([f for f in os.listdir(IMAGE_PATH) if f.lower().endswith('jpg') or f.lower().endswith('png') or f.lower().endswith('jpeg')])
    try_sample = st.sidebar.checkbox('Try Sample Images')
    if try_sample:
        select_image = st.sidebar.selectbox("Select a Sample Images", sample_images)
    else:
        # file upload
        # TODO: INTEGRATE FILE UPLOAD WITH IMAGE SELECTION
        upload_image = st.sidebar.file_uploader("Or Upload an Image", type=['jpg', 'png', 'jpeg'])


    # select confidence level
    conf = st.sidebar.slider('Face Detection Threshold (Higher => Less Faces)', 0.15, 0.85, 0.40)
    show_mask_result = st.sidebar.checkbox('Show Mask Detection Result')

    # process image
    opencv_image = None
    if not try_sample and upload_image is not None:
        # convert the file to an opencv image.
        opencv_image = cv2.cvtColor(np.array(Image.open(upload_image)), cv2.COLOR_BGR2RGB)
    elif try_sample:
        # use selected sample
        opencv_image = cv2.imread(os.path.join(IMAGE_PATH, select_image))
    else:
        st.write("Select or upload an image to begin")

    if opencv_image is not None:
        orig_image = opencv_image.copy()
    else:
        orig_image = None
    results = []
    result_img = None
    if show_mask_result and opencv_image is not None:
        result_img, results, face_counts = mask_detection(opencv_image, conf)
        st.image(result_img, channels="BGR", caption='face mask detection result', use_column_width=True)
        st.write("Detected **%d** faces with current threshold **%.2f**"%(face_counts[0], conf))
        if face_counts[0] != face_counts[1] or face_counts[0] != face_counts[2]:
            st.write("*You can modify the threshold to tune detection results:*")
            st.write("**%d** faces with threshold **%.2f**; **%d** faces with threshold **%.2f**"%(face_counts[1], 0.25, face_counts[2], 0.75))
    elif opencv_image is not None:
        result_img = st.image(opencv_image, channels="BGR", caption='selected image', use_column_width=True)
    return results, result_img, orig_image

def calculate_distance(results, image, avg_face_width=20):
    # reference object

    if len(results) > 1:
        min_dist = {}
        for i in range(len(results)):
            cX = (results[i]["cord"][0] + results[i]["cord"][2]) // 2
            cY = (results[i]["cord"][1] + results[i]["cord"][3]) // 2

            D = results[i]["cord"][3] - results[i]["cord"][1]
            refObj = (results[i], (cX, cY), D / avg_face_width)
            for j in range(len(results)):
                if i != j:
                    cX_2 = (results[j]["cord"][0] + results[j]["cord"][2]) // 2
                    cY_2 = (results[j]["cord"][1] + results[j]["cord"][3]) // 2

                    D_2 = np.linalg.norm(np.array(refObj[1]) - np.array((cX_2, cY_2))) / refObj[2]

                    if i not in min_dist or j not in min_dist or min_dist[i][0] > D_2:
                        new_distance = D_2
                        min_dist[i] = (new_distance, (cX, cY), (cX_2, cY_2), (i, j))
                        min_dist[j] = (new_distance, (cX, cY), (cX_2, cY_2), (i, j))
        
        visited = set()
        for key in min_dist:
            if key not in visited:
                dist = min_dist[key]
                distance, (cX, cY), (cX_2, cY_2), (i, j) = dist
                D = results[j]["cord"][3] - results[j]["cord"][1]
                ratio = D / avg_face_width
                D_2 = np.linalg.norm(np.array((cX_2, cY_2)) - np.array((cX, cY))) / ratio
                new_distance = (D_2 + distance) / 2
                min_dist[i] = (new_distance, (cX, cY), (cX_2, cY_2), (i, j))
                min_dist[j] = (new_distance, (cX, cY), (cX_2, cY_2), (i, j))
                visited.add(i)
                visited.add(j)
        
        orig = image.copy()
        drawn = set()
        count = 0
        distance_drawn = []
        total_score = 0
        for key in min_dist:
            dist = min_dist[key]
            i, j = dist[3]
            if i not in drawn or j not in drawn:
                drawn.add(i)
                drawn.add(j)

                color = (0, 255, 0)
                scale = 1
                if results[i]["prob"] < 0 and results[j]["prob"] < 0:
                    color = (0, 0, 255)
                    scale = 6
                elif results[i]["prob"] < 0 or results[j]["prob"] < 0:
                    color = (0, 165, 255)
                    scale = 3
                else:
                    color = (0, 255, 0)
                    scale = 1
                
                total_score += (scale / dist[0])
                distance_drawn.append(dist[0])
                count += 1

                cv2.line(orig, dist[1], dist[2], color, 2)
                mX = (dist[1][0] + dist[2][0]) // 2
                mY = (dist[1][1] + dist[2][1]) // 2
                font_scale = 0.6
                cv2.putText(orig, "{:.1f} cm".format(dist[0]), (int(mX), int(mY - 20)),
                cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, 2)
                cv2.putText(orig, "{:.1f} ft".format(dist[0]/30.48), (int(mX), int(mY + 20)),
                cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, 2)
        
        st.image(orig, channels="BGR", caption="distance between " + str(len(results)) + " persons", use_column_width=True)
        average_density = total_score / count
        average_distance = np.average(distance_drawn)
        st.write("The average distance between people is {:.1f} cm, roughly {:.1f} ft".format(average_distance, average_distance/30.48))
        if average_density > 12 / 182.88:
            st.write("The safety score is {:.4f}, chance of contracting COVID: **very high**".format(average_density*100))
        elif average_density > 9 / 182.88:
            st.write("The safety score is {:.4f}, chance of contracting COVID: **high**".format(average_density*100))
        elif average_density > 6 / 182.88:
            st.write("The safety score is {:.4f}, chance of contracting COVID: **medium**".format(average_density*100))
        elif average_density > 4 / 182.88:
            st.write("The safety score is {:.4f}, chance of contracting COVID: **low**".format(average_density*100))
        else:
            st.write("The safety score is {:.4f}, chance of contracting COVID: **very low**".format(average_density*100))
        st.write("The safety score is calculated as a density measure of mask per centimeter")
        st.write("- A density score above 6.56 indicates a high possibility of majority people not wearing mask in the scence")
        st.write("- A density score between 6.56 and 2.19 indicates a high possibility that more than 50% people in the scene wears a mask or majority obeys social distancing rules")
        st.write("- A density score of below 2.19 indicates that all the people are wearing mask and obeying social distancing rules")
    elif len(results) == 1:
        st.write("Only 1 person in the image, chance of contracting COVID: **low**")
    else:
        st.write("Please run the face detector first")

# TODO: IMPLEMENT SCORING MODEL
def calculate_score(results, result_img, orig_image):
    scale = st.sidebar.slider('Distance Scale', 12, 28, 20)
    show_eval = st.sidebar.checkbox('Show Safety Level Evaluation')

    if show_eval:
        st.subheader("Safety Level Evaluation")
        calculate_distance(results, result_img, avg_face_width=scale)
        if len(results) > 0:
            show_after_mask = st.sidebar.checkbox('Let More People Wear Mask')
            if show_after_mask and orig_image is not None:
                st.subheader("If more people start to wear masks")
                put_mask_on(results, orig_image, avg_face_width=scale)

def put_mask_on(results, orig_image, avg_face_width):
    mask_img = cv2.imread("Surgical-Mask.png", cv2.IMREAD_UNCHANGED)
    count = 0
    for i in range(len(results)):
        if results[i]["prob"] < 0:
            cY = (results[i]["cord"][1] + results[i]["cord"][3]) // 2

            resized = cv2.resize(mask_img, (results[i]["cord"][2] - results[i]["cord"][0], results[i]["cord"][3] - cY))
            for x in range(cY, results[i]["cord"][3]):
                for y in range(results[i]["cord"][0], results[i]["cord"][2]):
                    if resized[x-cY, y-results[i]["cord"][0], 3] != 0:
                        orig_image[x, y] = resized[x-cY, y-results[i]["cord"][0], :3]
            results[i]["prob"] *= -1
            count += 1
    if count != len(results):
        percentage_increase = count/(len(results)-count)*100
    else:
        percentage_increase = 100
    st.write("This is a {:.2f} percent increase for people wearing masks".format(percentage_increase))
    st.image(orig_image, channels="BGR", caption=str(count) + " more persons start to wear masks", use_column_width=True)
    st.subheader("Let's see how this change the situation")
    calculate_distance(results, orig_image, avg_face_width)

if __name__ == '__main__':
    show_visualization()
    results, result_img, orig_image = process_mask_image()
    calculate_score(results, result_img, orig_image)
   
