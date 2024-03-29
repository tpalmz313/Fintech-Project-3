##########################
# commodities page setup #
##########################

#pip install yfinance
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import yfinance as yf
import webbrowser
from PIL import Image

########################
# Technical Indicators #
########################

# Create a Mixin of interdependent non-side-effect-free code that is shared between components.
class IndicatorMixin:

    _fillna = False
    # check nulls
    def _check_fillna(self, series: pd.Series, value: int = 0) -> pd.Series:

        if self._fillna:
            series_output = series.copy(deep=False)
            series_output = series_output.replace([np.inf, -np.inf], np.nan)
            if isinstance(value, int) and value == -1:
                series = series_output.fillna(method="ffill").fillna(value=-1)
            else:
                series = series_output.fillna(method="ffill").fillna(value)
        return series

    @staticmethod
    # define the True Range which is the greatest distance you can find between any two of these three prices.
    def _true_range(
        high: pd.Series, low: pd.Series, prev_close: pd.Series
    ) -> pd.Series:
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        true_range = pd.DataFrame(data={"tr1": tr1, "tr2": tr2, "tr3": tr3}).max(axis=1)
        return true_range

# define dropna function
def dropna(df: pd.DataFrame) -> pd.DataFrame:
    # Drop rows with null values
    df = df.copy()
    number_cols = df.select_dtypes("number").columns.to_list()
    df[number_cols] = df[number_cols][df[number_cols] < math.exp(709)]  # big number
    df[number_cols] = df[number_cols][df[number_cols] != 0.0]
    df = df.dropna()
    return df

# define simple moving average (SMA)
def _sma(series, periods: int, fillna: bool = False):
    min_periods = 0 if fillna else periods
    return series.rolling(window=periods, min_periods=min_periods).mean()

# define exponential moving average (EMA) that places a greater weight and significance on the most recent data points.
def _ema(series, periods, fillna=False):
    min_periods = 0 if fillna else periods
    return series.ewm(span=periods, min_periods=min_periods, adjust=False).mean()

# Calling min() and max() With a Single Iterable Argument
def _get_min_max(series1: pd.Series, series2: pd.Series, function: str = "min"):
    # Find min or max value between two lists for each index
    series1 = np.array(series1)
    series2 = np.array(series2)
    if function == "min":
        output = np.amin([series1, series2], axis=0)
    elif function == "max":
        output = np.amax([series1, series2], axis=0)
    else:
        raise ValueError('"f" variable value should be "min" or "max"')

    return pd.Series(output)

# Setup BollingerBands
class BollingerBands(IndicatorMixin):
    # The __init__ function is called every time an object is created from a class
    def __init__(
        self,
        close: pd.Series,
        window: int = 20,
        window_dev: int = 2,
        fillna: bool = False,
    ):
        self._close = close
        self._window = window
        self._window_dev = window_dev
        self._fillna = fillna
        self._run()
    # define the BollingerBands run function
    def _run(self):
        min_periods = 0 if self._fillna else self._window
        self._mavg = self._close.rolling(self._window, min_periods=min_periods).mean()
        self._mstd = self._close.rolling(self._window, min_periods=min_periods).std(
            ddof=0
        )
        self._hband = self._mavg + self._window_dev * self._mstd
        self._lband = self._mavg - self._window_dev * self._mstd
    # define bollinger moving average Bollinger, channel middle band and returns pandas.Series new feature generated
    def bollinger_mavg(self) -> pd.Series:
        mavg = self._check_fillna(self._mavg, value=-1)
        return pd.Series(mavg, name="mavg")
    # Add bollinger band high indicator filling nans values, channel middle band and returns pandas.Series new feature generated
    def bollinger_hband(self) -> pd.Series:
        hband = self._check_fillna(self._hband, value=-1)
        return pd.Series(hband, name="hband")
    # Add bollinger band low indicator filling nans values, channel lower band and returns pandas.Series new feature generated
    def bollinger_lband(self) -> pd.Series:
        lband = self._check_fillna(self._lband, value=-1)
        return pd.Series(lband, name="lband")
    # Add bollinger band width indicator filling nans values, channel width band and returns pandas.Series new feature generated
    def bollinger_wband(self) -> pd.Series:
        wband = ((self._hband - self._lband) / self._mavg) * 100
        wband = self._check_fillna(wband, value=0)
        return pd.Series(wband, name="bbiwband")
    # Add bollinger band percentage indicator filling nans values, channel percentage band and returns pandas.Series new feature generated
    def bollinger_pband(self) -> pd.Series:
        pband = (self._close - self._lband) / (self._hband - self._lband)
        pband = self._check_fillna(pband, value=0)
        return pd.Series(pband, name="bbipband")
    # Bollinger Channel Indicator Crossing High Band (binary). It returns 1, if close is higher than bollinger_hband. Else, it returns 0 and returns pandas.Series new feature generated
    def bollinger_hband_indicator(self) -> pd.Series:
        hband = pd.Series(
            np.where(self._close > self._hband, 1.0, 0.0), index=self._close.index
        )
        hband = self._check_fillna(hband, value=0)
        return pd.Series(hband, index=self._close.index, name="bbihband")
    # Bollinger Channel Indicator Crossing Low Band (binary). It returns 1, if close is lower than bollinger_lband. Else, it returns 0 and returns pandas.Series new feature generated
    def bollinger_lband_indicator(self) -> pd.Series:
        lband = pd.Series(
            np.where(self._close < self._lband, 1.0, 0.0), index=self._close.index
        )
        lband = self._check_fillna(lband, value=0)
        return pd.Series(lband, name="bbilband")

# Relative Strength Index (RSI) Compares the magnitude of recent gains and losses over a specified time period to measure speed and change of price movements of a security. It is primarily used to attempt to identify overbought or oversold conditions in the trading of an asset.
class RSIIndicator(IndicatorMixin):
    # The __init__ function is called every time an object is created from a class
    def __init__(self, close: pd.Series, window: int = 14, fillna: bool = False):
        self._close = close
        self._window = window
        self._fillna = fillna
        self._run()
    # define the Relative Strength Index run function
    def _run(self):
        diff = self._close.diff(1)
        up_direction = diff.where(diff > 0, 0.0)
        down_direction = -diff.where(diff < 0, 0.0)
        min_periods = 0 if self._fillna else self._window
        emaup = up_direction.ewm(
            alpha=1 / self._window, min_periods=min_periods, adjust=False
        ).mean()
        emadn = down_direction.ewm(
            alpha=1 / self._window, min_periods=min_periods, adjust=False
        ).mean()
        relative_strength = emaup / emadn
        self._rsi = pd.Series(
            np.where(emadn == 0, 100, 100 - (100 / (1 + relative_strength))),
            index=self._close.index,
        )
    # define Relative Strength Index (RSI) check nulls and returns pandas.Series new feature generated
    def rsi(self) -> pd.Series:
        rsi_series = self._check_fillna(self._rsi, value=50)
        return pd.Series(rsi_series, name="rsi")

# Moving Average Convergence Divergence (MACD) Is a trend-following momentum indicator that shows the relationship between two moving averages of prices.
class MACD(IndicatorMixin):
    # The __init__ function is called every time an object is created from a class
    def __init__(
        self,
        close: pd.Series,
        window_slow: int = 26,
        window_fast: int = 12,
        window_sign: int = 9,
        fillna: bool = False,
    ):
        self._close = close
        self._window_slow = window_slow
        self._window_fast = window_fast
        self._window_sign = window_sign
        self._fillna = fillna
        self._run()
    # define the Moving Average Convergence Divergence (MACD) run function
    def _run(self):
        self._emafast = _ema(self._close, self._window_fast, self._fillna)
        self._emaslow = _ema(self._close, self._window_slow, self._fillna)
        self._macd = self._emafast - self._emaslow
        self._macd_signal = _ema(self._macd, self._window_sign, self._fillna)
        self._macd_diff = self._macd - self._macd_signal
    # define MACD line, check nulls and returns pandas.Series new feature generated
    def macd(self) -> pd.Series:
        macd_series = self._check_fillna(self._macd, value=0)
        return pd.Series(
            macd_series, name=f"MACD_{self._window_fast}_{self._window_slow}"
        )
    # define MACD signal, check nulls and returns pandas.Series new feature generated
    def macd_signal(self) -> pd.Series:
        macd_signal_series = self._check_fillna(self._macd_signal, value=0)
        return pd.Series(
            macd_signal_series,
            name=f"MACD_sign_{self._window_fast}_{self._window_slow}",
        )
    # define MACD histogram, check nulls and returns pandas.Series new feature generated
    def macd_diff(self) -> pd.Series:
        macd_diff_series = self._check_fillna(self._macd_diff, value=0)
        return pd.Series(
            macd_diff_series, name=f"MACD_diff_{self._window_fast}_{self._window_slow}"
        )

# The Rate-of-Change (ROC) indicator, which is also referred to as simply Momentum, is a pure momentum oscillator. The ROC calculation compares the current price with the price "n" periods ago
class ROCIndicator(IndicatorMixin):
    # The __init__ function is called every time an object is created from a class
    def __init__(self, close: pd.Series, window: int = 12, fillna: bool = False):
        self._close = close
        self._window = window
        self._fillna = fillna
        self._run()
    # define the rate of change run function
    def _run(self):
        self._roc = (
            (self._close - self._close.shift(self._window))
            / self._close.shift(self._window)
        ) * 100
    # define rate of change, check nulls and returns pandas.Series new feature generated
    def roc(self) -> pd.Series:
        roc_series = self._check_fillna(self._roc)
        return pd.Series(roc_series, name="roc")

# The true strength index (TSI) is a technical momentum oscillator used to identify trends and reversals. The indicator may be useful for determining overbought and oversold conditions, indicating potential trend direction changes via centerline or signal line crossovers, and warning of trend weakness through divergence.
class TSIIndicator(IndicatorMixin):
    # The __init__ function is called every time an object is created from a class
    def __init__(
        self,
        close: pd.Series,
        window_slow: int = 25,
        window_fast: int = 13,
        fillna: bool = False,
    ):
        self._close = close
        self._window_slow = window_slow
        self._window_fast = window_fast
        self._fillna = fillna
        self._run()
    # define the true strength index run function
    def _run(self):
        diff_close = self._close - self._close.shift(1)
        min_periods_r = 0 if self._fillna else self._window_slow
        min_periods_s = 0 if self._fillna else self._window_fast
        smoothed = (
            diff_close.ewm(
                span=self._window_slow, min_periods=min_periods_r, adjust=False
            )
            .mean()
            .ewm(span=self._window_fast, min_periods=min_periods_s, adjust=False)
            .mean()
        )
        smoothed_abs = (
            abs(diff_close)
            .ewm(span=self._window_slow, min_periods=min_periods_r, adjust=False)
            .mean()
            .ewm(span=self._window_fast, min_periods=min_periods_s, adjust=False)
            .mean()
        )
        self._tsi = smoothed / smoothed_abs
        self._tsi *= 100
    # define the true strength index, check nulls and returns pandas.Series new feature generated
    def tsi(self) -> pd.Series:
        tsi_series = self._check_fillna(self._tsi, value=0)
        return pd.Series(tsi_series, name="tsi")

##################
# Set up sidebar #
##################
# set sidebar title 
st.sidebar.title('Commodities Dashboard :oil_drum:')
# url = 'https://finance.yahoo.com/commodities'
# # add a button to open the yahoo finance website
# if st.sidebar.button('Yahoo! Commodities'):
#     webbrowser.open_new_tab(url)
    
# from PIL import Image 
image = Image.open('./images/gold.png')
st.sidebar.image(image)
# load stock symbols list
option = st.sidebar.selectbox('Select a Commodity', ('GC=F','SI=F','ES=F','YM=F','NQ=F','RTY=F','ZB=F','ZN=F','ZF=F','ZT=F','MGC=F','SIL=F','PL=F','HG=F','PA=F','CL=F','HO=F','NG=F'))


# set date and calendar params with error detection
import datetime

today = datetime.date.today()
before = today - datetime.timedelta(days=730)
start_date = st.sidebar.date_input('Start date', before) 
end_date = st.sidebar.date_input('End date', today)
if start_date < end_date:
    st.sidebar.success('Start date: `%s`\n\nEnd date:`%s`' % (start_date, end_date))
else:
    st.sidebar.error('Error: End date must fall after start date.')
# add creator information
st.sidebar.caption('Presented by Jeff, Thomas and Ray :hotsprings:')

url = 'https://finance.yahoo.com/commodities'
# add a button to open the yahoo finance website
if st.sidebar.button('Yahoo! Commodities'):
    webbrowser.open_new_tab(url)
##############
# Stock data #
##############
# setup of the main body window
# create dataframe to get data from yahoo finance
df = yf.download(option,start= start_date,end= end_date, progress=False)
st.title(option)
st.caption("note: previous day's closing data")
st.dataframe(df.tail(1))

# add a progress bar
progress_bar = st.progress(0)
st.subheader('_Technical Indicators_')
st.markdown('##### Bollinger Bands®')
indicator_bb = BollingerBands(df['Close'])
# create the bollinger bands df
bb = df
bb['Bollinger_Band_High'] = indicator_bb.bollinger_hband()
bb['Bollinger_Band_Low'] = indicator_bb.bollinger_lband()
bb = bb[['Close','Bollinger_Band_High','Bollinger_Band_Low']]
# create the Moving Average Convergence Divergence (MACD) df
macd = MACD(df['Close']).macd()
# create the Relative Strength Index (RSI) df
rsi = RSIIndicator(df['Close']).rsi()
# create the True Strength Index (TSI) df
tsi = TSIIndicator(df['Close']).tsi()
# create the Rate of Change (ROC) df
roc = ROCIndicator(df['Close']).roc()

###################
# Set up main app #
###################
# plot the bollinger bands line chart
st.line_chart(bb)
# set the chickable button url detail
url = 'https://www.investopedia.com/articles/technical/102201.asp'
# create a button
if st.button('Bollinger Bands® FAQs'):
    webbrowser.open_new_tab(url)
# add a seperator line
progress_bar = st.progress(0)
# create a 2 column view
col1, col2 = st.columns(2)
# plot the Moving Average Convergence Divergence (MACD) line chart
with col1: 
    st.markdown('##### Moving Average Convergence Divergence (MACD)')
    st.area_chart(macd)
    # set the chickable button url detail
    url = 'https://www.investopedia.com/terms/m/macd.asp'
    # create a button
    if st.button('MACD FAQs'):
        webbrowser.open_new_tab(url)
# plot the Relative Strength Index (RSI) line chart     
with col2:
    st.markdown("##### Relative Strength Index (RSI)")
    st.line_chart(rsi)
    st.markdown(" ")
    # set the chickable button url detail
    url = 'https://www.investopedia.com/terms/r/rsi.asp'
    # create a button
    if st.button('Relative Strength Index (RSI) FAQs'):
        webbrowser.open_new_tab(url)
# add a seperator line
progress_bar = st.progress(0)
# create a 2 column view     
col1, col2 = st.columns(2)
# plot the True Strength Index (TSI) line chart
with col1: 
    st.markdown("##### True Strength Index (TSI)")
    st.line_chart(tsi)
    # set the chickable button url detail
    url = 'https://www.investopedia.com/terms/t/tsi.asp'
    # create a button
    if st.button('True Strength Index (TSI) FAQs'):
        webbrowser.open_new_tab(url)
# plot the Rate of Change (ROC) line chart
with col2:
    st.markdown("##### Rate of Change (ROC)")
    st.line_chart(roc)
    # set the chickable button url detail
    url = 'https://www.investopedia.com/terms/r/rateofchange.asp'
    # create a button
    if st.button('Rate of Change (ROC) FAQs'):
        webbrowser.open_new_tab(url)
# add a seperator line
progress_bar = st.progress(0)
# display a snapshot of the df data        
st.markdown("##### 10 Day Snapshot :chart_with_upwards_trend:")
st.write(option)
st.dataframe(df.tail(10))
# add a seperator line
progress_bar = st.progress(0)

################
# Download csv #
################

# load imports
import base64
from io import BytesIO
# define the excel function
def to_excel(df):
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, sheet_name='Sheet1')
    writer.save()
    processed_data = output.getvalue()
    return processed_data

def get_table_download_link(df):
    val = to_excel(df)
    b64 = base64.b64encode(val)
    return f'<a href="data:application/octet-stream;base64,{b64.decode()}" download="download.xlsx">Download excel file</a>'
# define section title and download link
st.markdown(" ")
st.markdown("##### Create Stock Report :pencil:")
st.markdown(get_table_download_link(df), unsafe_allow_html=True)
# define the csv dataframe function
@st.cache
def convert_df(df):
    return df.to_csv().encode('utf-8')

csv = convert_df(df)
# create the csv file button and download details
st.download_button(
    label="Download data as CSV",
    data=csv,
    file_name='stocks.csv',
    mime='text/csv',
)
# create a PDF report
from fpdf import FPDF
import base64

pdf = FPDF()  # pdf object
pdf = FPDF(orientation="P", unit="mm", format="A4")
pdf.add_page()

pdf.set_font("Times", "B", 18)
pdf.set_xy(10.0, 20)
pdf.cell(w=75.0, h=5.0, align="L", txt="Future Enhancement - BETA Development")

st.download_button(
    "Download PDF Report",
    data=pdf.output(dest='S').encode('latin-1'),
    file_name="commodities.pdf",
    mime="application/octet-stream",
)
