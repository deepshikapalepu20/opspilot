import streamlit as st
import requests

st.set_page_config(
    page_title="OpsPilot",
    page_icon="🚨",
    layout="wide"
)

st.title("OpsPilot")
st.subheader("Agentic AI Incident Investigation")

st.write(
    "Enter an incident or investigation goal and OpsPilot "
    "will analyze the available operational evidence."
)

goal = st.text_area(
    "Investigation Goal",
    value="Investigate checkout-api latency spike",
    height=100
)

if st.button("Investigate", type="primary"):

    if not goal.strip():
        st.warning("Please enter an investigation goal.")
    else:

        with st.spinner("OpsPilot is investigating..."):

            try:
                response = requests.post(
                    "http://127.0.0.1:8000/investigate",
                    json={"goal": goal},
                    timeout=300
                )

                if response.status_code == 200:

                    result = response.json()

                    st.success("Investigation completed successfully!")

                    st.subheader("Investigation Result")

                    st.json(result)

                else:

                    st.error(
                        f"API returned status code "
                        f"{response.status_code}"
                    )

                    st.code(response.text)

            except requests.exceptions.ConnectionError:

                st.error(
                    "Could not connect to the OpsPilot API. "
                    "Make sure the FastAPI server is running."
                )

            except Exception as e:

                st.error(f"Unexpected error: {e}")