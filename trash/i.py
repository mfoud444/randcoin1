In the Binance platform and using Python I want do
python-binance
Specify the number of times fixed 4 times
Specify the number of minutes each time, for example 20 minutes start from now time 


step1 : get all coins and Filter only USDT pairs(note make code custimaze has  2 options if get all coins or only specific list coins)
step2 :  Fetch price data at time for every intervals and Store the results in a DataFrame for every intervals
step3: Compute percentage changes between consecutive prices and save the finalys information stticas  results in a new DataFrame with Assign positive or negative points based on the direction of the price change.
 Calculate percentage change   percentage_change = ((close_price - open_price) / open_price) * 100
Any information that may be important for decision making and understanding the logic: and clarifying how much the profit percentage will be above the capital if it is, for example, $100 if you invest in each stage.
simulate the effect of reinvesting gains/losses.
Display investment outcomes based on the changes after discount TRADING_FEE = 0.001  # 0.1% per trade  for every coins by every interval
simulate if i am goals get PROFIT_TARGET = 0.01  # 5% net profit target after discount TRADING_FEE = 0.001  # 0.1% per trade ir not and if yes how many long time nedded for that for every coins by every interval

Filter the coins if positive coins is zero or the negative > positive

note the gole this process is find fast coin movment and  get maximim profite  in fast way for scapling trending 

use tqdm and print any process 
write clean code and more readable and usedable 
use multithreading to fetch data for all coins simultaneously.
Donot add comments when write code 
added Error Handling
alwais can Customize Parameters

client = Client(api_key, api_secret, tld='us')


Addition:

U can finally add code Visualization
from this information pass information for 3 top coins to ai by choose best  and best 



