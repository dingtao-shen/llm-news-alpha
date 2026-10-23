# 摘要提示词对比：v1 vs v2，50 条真实新闻（seed 0）

自动线索只是提示：new_numbers / new_names = 摘要里出现、原文里没有的数字 / 大写词；omission = 出现「未披露」类措辞。请人工判断哪一版加料更少。

## 汇总（自动线索）

| 版本 | 出现「未披露」措辞 | 含原文没有的数字 | 含原文没有的大写词 | 平均句数 | 平均输出 token |
| --- | ---: | ---: | ---: | ---: | ---: |
| v1 | 3 | 23 | 3 | 1.8 | 58 |
| v2 | 0 | 25 | 3 | 2.0 | 63 |

## 1. [CPRT] Copart (CPRT) Is Up 0.04% in One Week: What You Should Know
*nasdaq.com, 2019-02-04*

> Momentum investing is all about the idea of following a stock's recent trend, which can be in either direction. In the 'long' context, investors will essentially be "buying high, but hoping to sell even higher." And for investors following this methodology, taking advantage of trends in a stock's price is key; once a stock establishes a course, it is more than likely to continue moving in that direction. The goal is that once a stock heads down a fixed path, it will lead to timely and profitable trades. Even though momentum is a popular stock characteristic, it can be tough to define. Debate surrounding which are the best and worst metrics to focus on is lengthy, but the Zacks Momentum Style …

**v1** (105 tok, ⚠nums['500.']): Copart (CPRT) is up 0.04% in one week, with shares rising 8.59% in the last month and 16.74% in the last year, outperforming the S&P 500. The company has a Zacks Rank of #2 (Buy) and a Momentum Style Score of B, with 1 earnings estimate revised higher in the past two months and a consensus estimate increase from $2.11 to $2.12 in the past 60 days.

**v2** (128 tok, ⚠nums['1,117,434']): Copart (CPRT) shares are up 0.04% over the past week, outperforming the Zacks Auction and Valuation Services industry's 3.24% decline. The company's shares have risen 8.59% in the past month and 16.74% in the last year, compared to the S&P 500's -0.71% and -2.3% performance, respectively. The company's average 20-day trading volume is 1,117,434 shares. Over the past two months, 1 earnings estimate moved higher for the full year, increasing the consensus estimate from

## 2. [ARE] Key Factors to Impact Prologis' (PLD) Earnings This Season
*nasdaq.com, 2018-01-19*

> Prologis, Inc.PLD is slated to report fourth-quarter 2017 earnings on Jan 23, before the opening bell. Last quarter, this industrial real estate investment trust (REIT) reported an in-line result in terms of funds from operations (FFO) per share. Though the company experienced improved operating environment in the quarter, it did not recognize any promote income. However, Prologis has a mixed surprise history. The company surpassed the FFO per share estimates in two occasions and met in the other two, over the preceding four quarters, resulting in an average positive surprise of 2.33%. This is depicted in the graph below: The Zacks Consensus Estimate for the fourth-quarter FFO per share is c …

**v1** (56 tok, ⚠nums['23,'] ⚠names['January']): Prologis, Inc. (PLD) is scheduled to report fourth-quarter 2017 earnings on January 23, before the opening bell. The Zacks Consensus Estimate for funds from operations (FFO) per share is currently pegged at 66 cents.

**v2** (47 tok, ⚠nums['23.'] ⚠names['January']): Prologis, Inc. (PLD) is scheduled to report fourth-quarter 2017 earnings on January 23. The Zacks Consensus Estimate for funds from operations (FFO) per share is 66 cents.

## 3. [GE] GE Healthcare, Ulrich Join To Bring Branded Multi-dose Contrast Media Injector In The U.S.
*nasdaq.com, 2022-11-28*

> (RTTNews) - GE Healthcare has entered an agreement with ulrich medical for a GE Healthcare branded contrast media injector in the U.S. The CT motion multi-dose syringeless injector, which delivers iodinated contrast media for Computed Tomography imaging procedures, reduces procedure setup time and increases patient throughput. CT motion, developed by ulrich medical, is already used globally. For the U.S. market, the CT motion injector is manufactured in Germany and shipped, distributed and serviced by GE Healthcare. The company noted that the U.S. contrast media injector market is estimated to grow at 4.3 percent annually between 2022-2030. For More Such Health News, visit rttnews.com. The v …

**v1** (51 tok): GE Healthcare has entered an agreement with Ulrich Medical to bring a branded multi-dose contrast media injector, CT motion, to the U.S. market. The injector, manufactured in Germany, will be shipped, distributed, and serviced by GE Healthcare.

**v2** (51 tok): GE Healthcare has entered an agreement with Ulrich Medical to bring a branded multi-dose contrast media injector, CT motion, to the U.S. market. The injector, manufactured in Germany, will be shipped, distributed, and serviced by GE Healthcare.

## 4. [HUM] Humana to exit employer insurance business to focus on government plans
*nasdaq.com, 2023-02-23*

> Adds background, share movement and details on membership for Medicare program Feb 23 (Reuters) - Humana Inc HUM.N will exit the employer-based insurance business over the next 18 to 24 months, it said on Thursday, to focus primarily on government-backed programs such as Medicare for people aged 65 and older and its specialty businesses. The U.S. insurer raised its forecast for the Medicare Advantage program it sells directly to individuals to at least 775,000 members from 625,000 on higher-than-anticipated sales and retention early in this year. Shares of the company rose as much as 1.3% to about $510 in early trading. "The exit from the commercial group business makes strategic sense as it …

**v1** (38 tok): Humana Inc (HUM) will exit its employer-based insurance business over the next 18-24 months to focus on government-backed programs, including Medicare Advantage, and specialty businesses.

**v2** (34 tok): Humana Inc will exit its employer-based insurance business over the next 18-24 months to focus on government-backed programs, including Medicare Advantage, and specialty businesses.

## 5. [DD] EI DuPont De Nemours & Co. Q2 23 Earnings Conference Call At 8:00 AM ET
*nasdaq.com, 2023-08-02*

> (RTTNews) - EI DuPont De Nemours & Co. (DD) will host a conference call at 8:00 AM ET on August 2, 2023, to discuss Q2 23 earnings results. To access the live webcast, log on to https://www.investors.dupont.com/investors/dupont-investors/default.aspx To listen to the call, dial 888-440-4172 or +1-646-960-0673, Conference ID 5994046. The views and opinions expressed herein are the views and opinions of the author and do not necessarily reflect those of Nasdaq, Inc.

**v1** (43 tok, ⚠nums['2,', '2023,']): EI DuPont De Nemours & Co. (DD) will host a conference call at 8:00 AM ET on August 2, 2023, to discuss Q2 23 earnings results.

**v2** (43 tok, ⚠nums['2,', '2023,']): EI DuPont De Nemours & Co. (DD) will host a conference call at 8:00 AM ET on August 2, 2023, to discuss Q2 23 earnings results.

## 6. [PM] Mid-Morning Market Update: Markets Mostly Lower; Philip Morris Shares Fall Following Q1 Results
*nasdaq.com, 2018-04-19*

> Following the market opening Thursday, the Dow traded up 0.04 percent to 24,758.25 while the NASDAQ declined 0.33 percent to 7,271.07. The S&P also fell, dropping 0.23 percent to 2,702.53. Leading and Lagging Sectors Thursday morning, the financial shares climbed 0.81 percent. Meanwhile, top gainers in the sector included American Express Company (NYSE: AXP ), up 6 percent, and Texas Capital Bancshares, Inc. (NASDAQ: TCBI ), up 7 percent. In trading on Thursday, consumer staples shares fell 2.78 percent. Top Headline Philip Morris International Inc. (NYSE: PM ) shares fell around 15 percent after the company reported better-than-expected profit for its first quarter, while revenue missed est …

**v1** (70 tok): Philip Morris International Inc. (PM) shares fell around 15% after the company reported Q1 earnings of $1 per share on revenue of $6.9 billion, missing revenue estimates, but raised its FY18 earnings outlook from $5.20-$5.35 per share to $5.25-$5.40 per share.

**v2** (76 tok): Philip Morris International Inc. (PM) reported Q1 earnings of $1 per share on revenue of $6.9 billion, missing revenue estimates. The company's shares fell around 15% following the results. Philip Morris also raised its FY18 earnings outlook from $5.20-$5.35 per share to $5.25-$5.40 per share.

## 7. [AAL] Notable Friday Option Activity: REGN, AAL, MCD
*nasdaq.com, 2021-08-13*

> Looking at options trading activity among components of the S&P 500 index, there is noteworthy activity today in Regeneron Pharmaceuticals, Inc. (Symbol: REGN), where a total volume of 3,213 contracts has been traded thus far today, a contract volume which is representative of approximately 321,300 underlying shares (given that every 1 contract represents 100 underlying shares). That number works out to 48.6% of REGN's average daily trading volume over the past month, of 661,740 shares. Particularly high volume was seen for the $625 strike call option expiring August 13, 2021, with 203 contracts trading so far today, representing approximately 20,300 underlying shares of REGN. Below is a cha …

**v1** (85 tok, ⚠nums['168,417', '17,', '2021,', '37,210']): American Airlines Group Inc (AAL) options have traded 168,417 contracts, representing approximately 16.8 million underlying shares, which is 48.3% of its average daily trading volume over the past month. High volume was seen for the $21 strike put option expiring September 17, 2021, with 37,210 contracts trading, representing approximately 3.7 million underlying shares.

**v2** (85 tok, ⚠nums['168,417', '17,', '2021,', '37,210']): American Airlines Group Inc (AAL) options have traded 168,417 contracts, representing approximately 16.8 million underlying shares, which is 48.3% of its average daily trading volume over the past month. High volume was seen for the $21 strike put option expiring September 17, 2021, with 37,210 contracts trading, representing approximately 3.7 million underlying shares.

## 8. [NEE] S&P 500 Analyst Moves: NEE
*nasdaq.com, 2019-11-07*

> The latest tally of analyst opinions from the major brokerage houses shows that among the components of the S&P 500 index, NextEra Energy is now the #16 analyst pick, moving up by 1 spot. This rank is formed by averaging the analyst opinions for each component from each broker, and then ranking the 500 components by those average opinion values. Looking at the stock price movement year to date, NextEra Energy is showing a gain of 27.9%. VIDEO: S&P 500 Analyst Moves: NEE The views and opinions expressed herein are the views and opinions of the author and do not necessarily reflect those of Nasdaq, Inc.

**v1** (38 tok): NextEra Energy (NEE) is now the #16 analyst pick, moving up 1 spot, and has a year-to-date stock price gain of 27.9%.

**v2** (36 tok): NextEra Energy (NEE) is now the #16 analyst pick, moving up 1 spot, and has a year-to-date gain of 27.9%.

## 9. [AMD] Chesapeake Energy Corporation (CHK) Stock Will Richly Reward the Bears
*nasdaq.com, 2017-06-02*

> InvestorPlace - Stock Market News, Stock Advice & Trading Tips Chesapeake Energy Corporation (NYSE: CHK ) has managed to astound many Wall Street participants as its conditions have somehow gone from bad to worse, both on and off the price chart. For as troubled as CHK stock has been, there always seems to be more bottom. Source: Philadelphia 76ers Via Flickr Today, I have a trade that we can use to harness Chesapeake's pain … without going into massive debt like CHK. Since writing about Chesapeake Energy stock in late April, it has been increasingly tough to justify owning the natural gas and oil outfit. In fact, I suggested a limited-risk strategy in lieu of shorting shares. And guess what …

**v1** (41 tok): No summary is needed as the article does not mention AMD. The article is about Chesapeake Energy Corporation (CHK) and discusses its stock performance, technical analysis, and a trading strategy for the stock.

**v2** (48 tok): No summary is needed as the article does not mention AMD (Advanced Micro Devices, Inc.) at all. The article is about Chesapeake Energy Corporation (CHK) and discusses its stock performance, technical analysis, and a potential trading strategy.

## 10. [INTC] Will the Driverless-Car Race End With a Tie?
*nasdaq.com, 2018-09-26*

> BMW AG (NASDAQOTH: BAMXF) is inviting its global rivals to join its self-driving effort. The company has already formed an alliance with several auto industry heavyweights and key technology firms that is aiming to deliver a new self-driving technology "platform" to theglobal marketby 2021 -- and its R&D chief wants other automakers to know that it's not too late to join the party. BMW is already working with rivals, and would welcome more In an interview this week, Klaus Froehlich, BMW's chief of research and development, told Automotive News Europe that many of the company's rivals are now confronting the difficulty of developing a full self-driving system from scratch. His message to them …

**v1** (39 tok): Intel (INTC) is a partner in BMW's self-driving effort, which aims to deliver a technology platform by 2021 that will be scalable and allow different levels of vehicle automation.

**v2** (78 tok): Intel (INTC) is a partner in BMW's self-driving effort, which aims to deliver a technology platform by 2021. The platform will be scalable, allowing different levels of vehicle automation, and BMW expects to launch it on its upcoming iNext electric crossover SUV in 2021. Other automakers can purchase the system for use in their own vehicles starting at that time.

## 11. [CVX] Game for Higher Returns? Bet on Jacobs' (JEC) Stock Now
*nasdaq.com, 2018-05-14*

> With 444 S&P 500 members having reported their quarterly figures as of May 9 , the first-quarter earnings season is nearing its last leg. Total earnings for these companies are up 24.5% year over year on 9.3% higher revenues, with 77.7% beating earnings estimates and 75% surpassing top-line expectations. This year's January-March earnings scorecard has been impressive, with the Construction sector currently ruling the roost among the 16 Zacks sectors. Increased public spending, lower tax rates, upbeat wage rates and reduced trade deficits are expected to propel the economic growth and augment aggregate construction spending in the country. Given this backdrop, investors can make the most of  …

**v1** (33 tok): CVX, Exxon Mobil Corporation, was mentioned as one of the public-sector agencies that Jacobs Engineering Group Inc. (JEC) has secured a contract from.

**v2** (31 tok): CVX, Exxon Mobil Corporation, was mentioned as one of the companies that Jacobs Engineering Group Inc. (JEC) has secured a contract from.

## 12. [DIS] Netflix Stock Opportunity Has Legs Heading Into 2020
*nasdaq.com, 2019-12-23*

> The good news is that Netflix (NASDAQ:) stock dug itself out of a hole, as it recently rallied sharply to catch up with the S&P 500 this year. Back in September, though, it was a different story. There were very few fans of Netflix stock as it was falling into an abyss, and the stock lost 33% from its 52-week high back in April before it finally bottomed. Source: Riccosta / Shutterstock.com Back then, I wrote about the opportunity of upside in NFLX because it had fallen into support. The lows from Christmas of last year turned out to indeed be solid footing for this rebound rally. Since then, NFLX stock mounted a 35% rally which should have more to go. This is a profit of $80 per share for t …

**v1** (49 tok, ⚠omission): There is no specific financial news article about Disney (DIS) in the provided text. The article discusses Netflix (NFLX) stock and its potential resistance level at $336 per share, as well as its competition from Disney and other companies.

**v2** (78 tok): Here is a summary of the article:

Netflix (DIS) stock has rallied 35% since its September lows, with a profit of $80 per share for those who bought in. The stock is approaching a resistance level at $336 per share, which it failed to break through in July. The author suggests exercising patience and waiting for a breakout confirmation before buying or selling the stock.

## 13. [FANG] Diamondback Energy Q3 21 Earnings Conference Call At 9:00 AM ET
*nasdaq.com, 2021-11-02*

> (RTTNews) - Diamondback Energy, Inc. (FANG) will host a conference call at 9:00 AM ET on November 2, 2021, to discuss Q3 21 earnings results. To access the live webcast, log on to https://www.diamondbackenergy.com/investors/events-presentations To listen to the call, dial (877) 440-7573 (US) or (253) 237-1144 (International) with confirmation code 7705208. For a replay call, dial (855) 859-2056 (US) or (404) 537-3406 (International) with confirmation code 7705208. The views and opinions expressed herein are the views and opinions of the author and do not necessarily reflect those of Nasdaq, Inc.

**v1** (41 tok, ⚠nums['2,', '2021,']): Diamondback Energy, Inc. (FANG) will host a conference call at 9:00 AM ET on November 2, 2021, to discuss Q3 21 earnings results.

**v2** (41 tok, ⚠nums['2,', '2021,']): Diamondback Energy, Inc. (FANG) will host a conference call at 9:00 AM ET on November 2, 2021, to discuss Q3 21 earnings results.

## 14. [ORCL] Courts Finds No Evidence Of Discrimination At Oracle
*nasdaq.com, 2020-09-22*

> (RTTNews) - Oracle Corp. (ORCL) said that the Department of Labor Administration Law Judge ruled in favor of the company and found no evidence whatsoever of discrimination at the company. "Oracle is run with equality and opportunity for all of our employees," said Joyce Westerdahl, Oracle's EVP for Human Resources. In a more than 200-page decision, Judge Clark found that Oracle did not engage in intentional compensation discrimination --wage-rate, salary, or total compensation-- at its headquarters facility during the relevant time period against female employees in the Product Development, Information Technology, and Support job functions; or against Asian and African American employees in  …

**v1** (76 tok): Oracle Corp. (ORCL) said that a Department of Labor Administration Law Judge ruled in favor of the company, finding no evidence of discrimination at the company. The Judge's decision, over 200 pages long, concluded that Oracle did not engage in intentional compensation discrimination or assignment, job classification, or steering discrimination against female or Asian/African American employees in certain job functions.

**v2** (66 tok): Oracle Corp. (ORCL) was found not to have engaged in discrimination by a Department of Labor Administration Law Judge, who ruled that the company did not have a policy or practice of relying on prior pay in salary setting, and did not show a disparate impact on female or Asian/African American employees in certain job functions.

## 15. [DISH] Notable Wednesday Option Activity: DISH, WYNN, ADS
*nasdaq.com, 2017-10-18*

> Among the underlying components of the S&P 500 index, we saw noteworthy options trading volume today in Dish Network Corp (Symbol: DISH), where a total of 21,414 contracts have traded so far, representing approximately 2.1 million underlying shares. That amounts to about 95.1% of DISH's average daily trading volume over the past month of 2.3 million shares. Especially high volume was seen for the $60 strike call option expiring March 16, 2018 , with 8,885 contracts trading so far today, representing approximately 888,500 underlying shares of DISH. Below is a chart showing DISH's trailing twelve month trading history, with the $60 strike highlighted in orange: Wynn Resorts Ltd (Symbol: WYNN)  …

**v1** (52 tok, ⚠nums['21,414', '8,885', '16,', '2018,', '888,500']): DISH: 21,414 contracts traded, representing 2.1 million underlying shares, with 8,885 contracts trading for the $60 strike call option expiring March 16, 2018, representing 888,500 underlying shares.

**v2** (60 tok, ⚠nums['21,414', '8,885', '16,', '2018,', '888,500']): Dish Network Corp (DISH) saw 21,414 contracts traded, representing approximately 2.1 million underlying shares, with 8,885 contracts trading for the $60 strike call option expiring March 16, 2018, representing approximately 888,500 underlying shares.

## 16. [DHR] Danaher Corp. Q4 adjusted earnings Beat Estimates
*nasdaq.com, 2021-01-28*

> (RTTNews) - Danaher Corp. (DHR) revealed earnings for fourth quarter that decreased from last year. The company's bottom line came in at $1.20 billion, or $1.66 per share. This compares with $1.26 billion, or $1.73 per share, in last year's fourth quarter. Analysts had expected the company to earn $1.87 per share, according to figures compiled by Thomson Reuters. Analysts' estimates typically exclude special items. The company's revenue for the quarter rose 38.8% to $6.76 billion from $4.87 billion last year. Danaher Corp. earnings at a glance: -EPS (Q4): $2.08 vs. $1.28 last year. -Analysts Estimate: $1.87 -Revenue (Q4): $6.76 Bln vs. $4.87 Bln last year. The views and opinions expressed he …

**v1** (48 tok): Danaher Corp. (DHR) reported Q4 adjusted earnings of $1.66 per share, beating estimates of $1.87 per share, with revenue up 38.8% to $6.76 billion.

**v2** (46 tok): Danaher Corp. reported Q4 adjusted earnings of $1.66 per share, beating the $1.87 per share expected by analysts, with revenue up 38.8% to $6.76 billion.

## 17. [AMGN] Amgen’s 1Q Results Disappoint; Shares Drop 8%
*nasdaq.com, 2021-04-28*

> Amgen’s (AMGN) shares fell around 8% in early trading on Wednesday as the biopharmaceutical company reported disappointing results. Revenues fell 4% year-on-year to $5.9 billion, missing analysts’ estimate of $6.3 billion. The company reported a 12% year-on-year decline in non-GAAP EPS to $3.70, missing consensus estimates of $4.04 per share. Amgen’s Chairman and CEO, Robert A. Bradway said, "While our business continued to be impacted by the COVID-19 pandemic particularly in the first two months of the quarter, we are encouraged by strong volume trends in many of our newer products and remain confident in the outlook for the full year.” “We also continue to advance key pipeline opportunitie …

**v1** (69 tok, ⚠nums['$3.70,']): Amgen (AMGN) reported 1Q results, with revenues falling 4% year-on-year to $5.9 billion, missing analysts' estimate of $6.3 billion, and non-GAAP EPS declining 12% year-on-year to $3.70, missing consensus estimates of $4.04 per share.

**v2** (69 tok, ⚠nums['$3.70,']): Amgen (AMGN) reported 1Q results, with revenues falling 4% year-on-year to $5.9 billion, missing analysts' estimate of $6.3 billion, and non-GAAP EPS declining 12% year-on-year to $3.70, missing consensus estimates of $4.04 per share.

## 18. [PXD] Pioneer Natural Resources Stock Getting Very Oversold
*nasdaq.com, 2021-07-16*

> In trading on Friday, shares of Pioneer Natural Resources Co (Symbol: PXD) entered into oversold territory, changing hands as low as $143.92 per share. We define oversold territory using the Relative Strength Index, or RSI, which is a technical analysis indicator used to measure momentum on a scale of zero to 100. A stock is considered to be oversold if the RSI reading falls below 30. In the case of Pioneer Natural Resources Co, the RSI reading has hit 29.1 — by comparison, the universe of energy stocks covered by Energy Stock Channel currently has an average RSI of 43.6, the RSI of WTI Crude Oil is at 46.6, the RSI of Henry Hub Natural Gas is presently 62.1, and the 3-2-1 Crack Spread RSI i …

**v1** (52 tok, ⚠nums['29.1,']): Pioneer Natural Resources Co (PXD) shares traded as low as $143.92 per share, entering oversold territory with an RSI reading of 29.1, compared to an average RSI of 43.6 among energy stocks.

**v2** (51 tok, ⚠nums['29.1,']): Pioneer Natural Resources Co (PXD) shares traded as low as $143.92 per share, entering oversold territory with an RSI reading of 29.1, below the average RSI of 43.6 for energy stocks.

## 19. [NVDA] Stock Market Today: New S&P, Nasdaq Highs Thanks to Apple, Nvidia
*nasdaq.com, 2021-11-18*

> The stock market lumbered through another tame session at the broader-index level Thursday, but a few exciting individual moves in Big Tech were just enough to get the S&P 500 and Nasdaq Composite back into record territory. Initial unemployment claims for the week ended Nov. 13 didn't seem to affect stocks much. The week's 268,000 filings were just barely more than expected (260,000), but also slightly lower than last week's upwardly revised 269,000. SEE MORE 10 Stocks Warren Buffett Is Selling (And 4 He's Buying) More encouraging was the Philly Fed, which showed activity jumping to 39.0 in November from 23.8 last month (any reading above zero is indicates growth). “The Philly Fed index was …

**v1** (53 tok): Nvidia (NVDA) reported a 50% year-over-year improvement in Q3 revenues and better-than-expected earnings, driven by a big quarter from its gaming and datacenter products, resulting in an 8.3% gain in stock price.

**v2** (53 tok): Nvidia (NVDA) reported a 50% year-over-year improvement in Q3 revenues and better-than-expected earnings, driven by a big quarter from its gaming and datacenter products, resulting in an 8.3% gain in stock price.

## 20. [MU] Micron Is Benefiting From These 2 Industry Trends
*nasdaq.com, 2022-07-02*

> It has been difficult historically to invest in Micron Technology (NASDAQ: MU) thanks to the highly cyclical nature of the semiconductor sector. In good times, profitability surges to the roof, but during bad times (which happen every few years), the bottom line could plunge into the red. But there are early signs that industry dynamics have been improving over the last few years. While the increase in memory demand -- thanks to trends like artificial intelligence (AI) adoption, 5G phones, and smart cars, to name a few -- is a significant driver, other less apparent shifts within the memory industry also contribute positively to the improving dynamics. Here are two of these less obvious tren …

**v1** (92 tok): Micron Technology (MU) has benefited from two industry trends: an increasingly rational supply addition and a vast and expanding barrier to entry. The former trend is characterized by slowing growth in transistor numbers and growing capital requirements, leading to more disciplined supply addition and reduced price competition. The latter trend is marked by a high barrier to entry due to the scale and complexity of memory and storage manufacturing, as well as intellectual property and technical know-how held by existing players.

**v2** (94 tok): Micron Technology (MU) has benefited from two industry trends: an increasingly rational supply addition and a vast and expanding barrier to entry. The slowing growth in transistor numbers and growing capital requirements have led to a more disciplined supply addition, reducing price competition and increasing industry gross margin. The high barrier to entry, with only a few global players and significant intellectual property and technical know-how, makes it difficult for new entrants to compete, benefiting existing players like Micron.

## 21. [XOM] EXCLUSIVE-U.S. driller Presidio in advanced talks to buy Exxon shale gas wells - sources
*nasdaq.com, 2021-12-20*

> By Shariq Khan Dec 20 (Reuters) - Presidio Petroleum LLC is in advanced talks to acquire around 5,000 shale gas wells from U.S. oil producer Exxon Mobil Corp XOM.N, two people familiar with the matter told Reuters on Monday. Exxon's XTO Energy unit has been seeking buyers for its holdings in the Fayetteville Shale in Arkansas, part of the company's drive to raise cash by shedding unwanted assets. Presidio, a closely-held producer backed by Morgan Stanley Energy Partners, buys mature oil and gas fields and strives to boost output. (Reporting by Shariq Khan in Bengaluru) ((shariq.khan@thomsonreuters.com; +1 469-691-7668;)) The views and opinions expressed herein are the views and opinions of t …

**v1** (30 tok, ⚠nums['5,000']): Exxon Mobil Corp (XOM) is in advanced talks to sell around 5,000 shale gas wells to Presidio Petroleum LLC.

**v2** (30 tok, ⚠nums['5,000']): Exxon Mobil Corp (XOM) is in advanced talks to sell around 5,000 shale gas wells to Presidio Petroleum LLC.

## 22. [COST] 2 Important Reasons to Invest in Costco Stock
*nasdaq.com, 2022-05-12*

> InvestorPlace - Stock Market News, Stock Advice & Trading Tips For a lot of retailers, 2022 has been a challenging year. Rising inflation rates have made it hard for customers to keep spending. In contrast, the stock market has continued to see sharp drops in value due to investor reluctance and anticipation of Federal Reserve action. However, a few stocks have managed to buck the trend, and Costco (NASDAQ:COST) is one such example. COST stock is up 24.8% over the past 12 months. It has made the company one of the rare gems in today’s market. Costco has managed to navigate the broad market problems and keep moving forward with its monthly sales and profits. Costco has proven time and time ag …

**v1** (70 tok, ⚠nums['2022.']): Costco (COST) stock is up 24.8% over the past 12 months, making it one of the rare gems in the market. The company has managed to navigate market problems and keep moving forward with its monthly sales and profits, with comps 14% higher than January 2020 averages in January 2022.

**v2** (58 tok): Costco (COST) stock is up 24.8% over the past 12 months, making it one of the few stocks to buck the trend in a challenging year. The company has a stable business model and has consistently increased profits and cash flow over the past decade.

## 23. [XOM] Exxon Mobil Corporation (XOM) Is a Trending Stock: Facts to Know Before Betting on It
*nasdaq.com, 2023-07-24*

> Exxon Mobil (XOM) is one of the stocks most watched by Zacks.com visitors lately. So, it might be a good idea to review some of the factors that might affect the near-term performance of the stock. Over the past month, shares of this oil and natural gas company have returned +1.5%, compared to the Zacks S&P 500 composite's +4% change. During this period, the Zacks Oil and Gas - Integrated - International industry, which Exxon falls in, has gained 2%. The key question now is: What could be the stock's future direction? While media releases or rumors about a substantial change in a company's business prospects usually make its stock 'trending' and lead to an immediate price change, there are a …

**v1** (128 tok): Exxon Mobil (XOM) has returned +1.5% over the past month, compared to the Zacks S&P 500 composite's +4% change and the Zacks Oil and Gas - Integrated - International industry's 2% gain. The company is expected to post earnings of $2.12 per share for the current quarter, a change of -48.8% from the year-ago quarter, and $9.11 for the current fiscal year, a change of -35.2% from the prior year. The Zacks Consensus Estimate has changed -8.7% over the last 30

**v2** (111 tok): Exxon Mobil (XOM) has returned +1.5% over the past month, compared to the Zacks S&P 500 composite's +4% change and the Zacks Oil and Gas - Integrated - International industry's 2% gain. The company is expected to post earnings of $2.12 per share for the current quarter, a change of -48.8% from the year-ago quarter, and $9.11 for the current fiscal year, a change of -35.2% from the prior year.

## 24. [GILD] Bursting Biotechs -- Are These Stocks Buys?
*nasdaq.com, 2015-09-08*

> Biotech is a favorite sector for us to talk about here at The Motley Fool, and with the recent hits the market has taken, some of these companies are looking like a steal. But are they worth jumping on board with during this downturn, or should we let clinical trials play out before we go all in? A full transcript follows the video. The next billion-dollar iSecret The world's biggest tech company forgot to show you something at its recent event, but a few Wall Street analysts and the Fool didn't miss a beat: There's a small company that's powering their brand-new gadgets and the coming revolution in technology. And we think its stock price has nearly unlimited room to run for early in-the-kn …

**v1** (104 tok, ⚠nums['9.']): Gilead Sciences' shares have dropped 12% to around $100 over the past month, but Todd Campbell believes the company is a buy. Gilead is a market leader in HIV treatment and hepatitis C treatment, generating significant revenue and profit. The company's trailing P/E ratio is 11 and forward P/E ratio is under 9. Campbell thinks Gilead's dominance in the hepatitis C market will continue, despite competition from other companies, and that the company's HIV business will remain strong.

**v2** (114 tok, ⚠nums['9,'] ⚠names['Despite']): Gilead Sciences' shares have dropped 12% to around $100 over the past month. Despite this, Todd Campbell believes the company is a buy, citing its dominant market position in HIV treatment and hepatitis C treatment, as well as its strong revenue and profit generation. He notes that the company's trailing P/E ratio is 11 and forward P/E ratio is under 9, making it an attractive valuation. Campbell also believes that the company's next-generation hepatitis C drug, which is expected to be filed this quarter, will help maintain its market share.

## 25. [ULTA] Ulta Beauty (ULTA) Stock Sinks As Market Gains: What You Should Know
*nasdaq.com, 2023-07-25*

> In the latest trading session, Ulta Beauty (ULTA) closed at $451.64, marking a -0.67% move from the previous day. This change lagged the S&P 500's 0.28% gain on the day. At the same time, the Dow added 0.08%, and the tech-heavy Nasdaq gained 0.61%. Coming into today, shares of the beauty products retailer had lost 1.92% in the past month. In that same time, the Retail-Wholesale sector gained 3.9%, while the S&P 500 gained 4.86%. Wall Street will be looking for positivity from Ulta Beauty as it approaches its next earnings report date. This is expected to be August 24, 2023. The company is expected to report EPS of $5.81, up 1.93% from the prior-year quarter. Meanwhile, our latest consensus e …

**v1** (56 tok, ⚠nums['$451.64,', '24,']): Ulta Beauty (ULTA) closed at $451.64, down 0.67% from the previous day, with expected EPS of $5.81 and revenue of $2.49 billion in its next earnings report on August 24, 2023.

**v2** (67 tok, ⚠nums['$451.64,', '24,']): Ulta Beauty (ULTA) closed at $451.64, down 0.67% from the previous day, while the S&P 500 gained 0.28%. The company is expected to report EPS of $5.81 and revenue of $2.49 billion on August 24, 2023.

## 26. [HPQ] HP Aims Its New Chromebooks at Apple and Microsoft
*nasdaq.com, 2018-04-16*

> HP (NYSE: HPQ) recently introduced the Chromebook x2, which features a 2-in-1 laptop design with a detachable Chrome OS tablet. The Chromebook x2 is the first detachable device running on Alphabet 's (NASDAQ: GOOG) (NASDAQ: GOOGL) Chrome OS, and technically the second Chrome OS tablet after Acer 's new Chromebook Tab 10. The Chromebook x2 targets both Windows convertibles and Apple 's (NASDAQ: AAPL) iPad Pro. The device has a 12.3" screen, compared to the iPad Pro's 12.9" display, and is only slightly thicker and heavier than the iPad Pro. The Chromebook x2 also has much beefier specs than an average tablet. The base model is equipped with Intel 's Core m3 CPU, 4GB of RAM, 32GB of storage, a …

**v1** (93 tok, ⚠nums['2,', '2,400', '1,600']): HP (HPQ) introduced the Chromebook x2, a 2-in-1 laptop with a detachable Chrome OS tablet, targeting Apple's iPad Pro and Microsoft's Surface Laptop. The device features a 12.3" screen, Intel Core m3 CPU, 4GB of RAM, 32GB of storage, and a 2,400 x 1,600 display, priced at $599 with a keyboard cover and stylus.

**v2** (89 tok, ⚠nums['2,', '2,400', '1,600']): HP introduced the Chromebook x2, a 2-in-1 laptop with a detachable Chrome OS tablet, targeting Apple's iPad Pro and Microsoft's Surface Laptop. The device features a 12.3" screen, Intel Core m3 CPU, 4GB of RAM, 32GB of storage, and a 2,400 x 1,600 display, priced at $599 with a keyboard cover and stylus.

## 27. [INTC] Intel (INTC) Stock Soars on Earnings Beat, Strong Guidance
*nasdaq.com, 2018-04-26*

> Intel Corporation (INTC) just released its latest quarterly financial results, posting adjusted earnings of 87 cents per share and revenues of $16.1 billion. Currently, INTC is a Zacks Rank #3 (Hold), but that could change based on today's results. Shares of the company have lost about 2% over the past month but added nearly 3.3% during regular trading hours today. The stock is currently up 8.3% to $57.44 per share in after-hours trading shortly after its earnings report was released. Intel: Beat earnings estimates . The company posted non-GAAP earnings of $0.87 per share, crushing the Zacks Consensus Estimate of $0.71. Investors should note that this consensus projection has trended upward  …

**v1** (43 tok): Intel Corporation (INTC) reported adjusted earnings of 87 cents per share and revenues of $16.1 billion, beating earnings estimates of $0.71 and revenue estimates of $15.05 billion.

**v2** (43 tok): Intel Corporation (INTC) reported adjusted earnings of 87 cents per share and revenues of $16.1 billion, beating earnings estimates of $0.71 and revenue estimates of $15.05 billion.

## 28. [BRK.B] Amazon's Retail & Budding Web Services Make It a Real Deal
*nasdaq.com, 2018-04-23*

> It's been 13 years of Amazon.com, Inc.'s AMZN Prime membership service. Now, the service has reached 100 million subscribers after adding more members in 2017 than in any other year. Amazon had shipped more than 5 billion items last year. CEO Jeff Bezos did update investors on a number of key milestones in his annual letter to shareholders, but, market pundits said that Prime subscriber numbers were the most encouraging. In fact, the total count of Amazon Web Services active users, including the Prime numbers, was up 250% last year. Amazon Web Services currently has nearly $20 billion in annual revenues. The company acknowledged 2017 as the best year for hardware sales. Among the products, t …

**v1** (38 tok): Warren Buffett, CEO of Berkshire Hathaway (BRK.B), admitted that he initially underestimated Amazon's value, calling Jeff Bezos the "most remarkable business person of our age."

**v2** (40 tok): Warren Buffett, CEO of Berkshire Hathaway (BRK.B), admitted he underestimated Amazon's (AMZN) value, calling Jeff Bezos the "most remarkable business person of our age."

## 29. [EBAY] Is Meritocracy a Joke for Women in Tech?
*nasdaq.com, 2015-04-12*

> From Patricia Arquette's passionate Oscars battle cry about gender pay disparity to the recent ruling against Ellen Pao in her gender discrimination lawsuit lobbed at Kleiner Perkins, how women fare in the workplace has been a big and often controversial topic recently. Many people who believe women are treated fairly in the workplace throw out the word "meritocracy" to explain discrepancies in pay and presence in leadership areas. However, that's becoming a flimsy, throwaway excuse aimed at a complicated issue. In many pockets of American business culture, the very definition of merit may be biased and flawed. Going negative The current situation in the tech industry has taken the issues of …

**v1** (42 tok): EBAY has been named as a company that will have a shareholder proposal filed regarding gender pay equity, requesting the company publicly disclose the pay differential between male and female employees and set goals to close the gap.

**v2** (67 tok): EBAY has been named as a company with a shareholder proposal regarding gender pay equity, requesting the tech giant publicly disclose the pay differential between male and female employees and set goals to close such a gap. The proposal was filed by Arjuna Capital and will be voted on by shareholders prior to the annual meeting on May 1.

## 30. [CHTR] November 18th Options Now Available For Charter Communications (CHTR)
*nasdaq.com, 2022-08-03*

> Investors in Charter Communications Inc (Symbol: CHTR) saw new options become available today, for the November 18th expiration. One of the key inputs that goes into the price an option buyer is willing to pay, is the time value, so with 107 days until expiration the newly available contracts represent a possible opportunity for sellers of puts or calls to achieve a higher premium than would be available for the contracts with a closer expiration. At Stock Options Channel, our YieldBoost formula has looked up and down the CHTR options chain for the new November 18th contracts and identified one put and one call contract of particular interest. The put contract at the $450.00 strike price has …

**v1** (74 tok, ⚠nums['$28.40,']): New options contracts for Charter Communications (CHTR) with an expiration date of November 18th are now available. The article highlights two specific contracts: a put contract at the $450.00 strike price with a current bid of $28.40, and a call contract at the $460.00 strike price with a current bid of $31.40.

**v2** (67 tok, ⚠nums['$28.40,']): New options contracts for Charter Communications (CHTR) with an expiration date of November 18th are now available. The put contract at the $450.00 strike price has a current bid of $28.40, and the call contract at the $460.00 strike price has a current bid of $31.40.

## 31. [MRK] 3 Value Stocks That'll Make You Richer in May (and Beyond)
*nasdaq.com, 2021-05-05*

> It's no secret that growth stocks have run circles around value stocks since the Great Recession ended in 2009. It's also plainly evident that historically low lending rates are working in favor of fast-growing businesses. But when it comes to long-term history, value stocks rule the roost. A 2016 report from Bank of America/Merrill Lynch examined the collective performance of growth stocks and value stocks over 90 years (1926-2015). While growth stocks averaged a healthy 12.6% annual gain over nine decades, it was the 17% average annual gain from value stocks that stood supreme. What's more, BofA/Merrill Lynch noted that value stocks have a tendency to significantly outperform growth stocks …

**v1** (128 tok, ⚠nums['2020,', '2019,', '2021,', '2021.']): Merck (MRK) reported Keytruda generated $14.4 billion in sales in 2020, a 30% increase from 2019, and $3.9 billion in sales in Q1 2021, a 19% increase from the prior-year period. The company's animal health division is rapidly growing, with a 26% revenue increase in Q1 2021. Merck is expected to grow sales by a mid-to-high single-digit percentage through at least mid-decade, with a forward price-to-earnings ratio of 10 and a 3.5% dividend yield.

**v2** (117 tok, ⚠nums['2020,', '2019,', '2021.']): Merck (MRK) reported Keytruda generated $14.4 billion in sales in 2020, a 30% increase from 2019, with first-quarter sales up 19% to $3.9 billion. The company's animal health division is rapidly growing, with a 26% revenue increase in Q1 2021. Merck is expected to grow sales by a mid-to-high single-digit percentage through at least mid-decade, with a forward price-to-earnings ratio of 10 and a 3.5% dividend yield.

## 32. [MCK] LabCorp (LH) to Report Q3 Earnings: What's in the Cards?
*nasdaq.com, 2022-10-17*

> Laboratory Corporation of America Holdings LH, also known as LabCorp, is slated to report third-quarter 2022 results on Oct 27, before market open. In the last reported quarter, the company’s adjusted earnings of $4.96 exceeded the Zacks Consensus Estimate by 6.2%. The company beat estimates in each of the trailing four quarters, the average surprise being 16.96%. Factors at Play LabCorp has been registering an ongoing sales rebound in the base business for both Diagnostics and Drug Development segments. However, as the severity of the pandemic has declined, we expect the demand for COVID-19 testing services and vaccines to have been lower than the year-ago period, impacting the third-quarte …

**v1** (23 tok, ⚠names['November']): McKesson (MCK) is scheduled to report third-quarter 2022 earnings on November 1.

**v2** (128 tok, ⚠nums['27.'] ⚠names['October']): Here is a summary of the article:

LabCorp (LH) is scheduled to report third-quarter 2022 results on October 27. The company's adjusted earnings of $4.96 in the last reported quarter exceeded the Zacks Consensus Estimate by 6.2%. The Zacks Consensus Estimate for LabCorp Diagnostics' third-quarter revenues is pegged at $2.28 billion, implying a 13.1% decline from the year-ago quarter's reported figure. The Zacks Consensus Estimate for third-quarter earnings is pegged at $4.72 per share, implying a 30.8%

## 33. [TAP] HEXO Stock Drops Following Analyst Downgrade
*nasdaq.com, 2020-02-21*

> HEXO (NYSE: HEXO) was hit by an analyst downgrade on Friday. In a research note, investment bank Jefferies Financial Group shifted its recommendation on the stock to underperform from the previous hold. It also cut its price target on the shares nearly in half, from 1.90 Canadian dollars ($1.43) to CA$1 ($0.75). In the note, analyst Owen Bennett opines that sales forecasts for marijuana and cannabis products in Canada are too optimistic. He also feels that the profitability of Cannabis 2.0 products -- the derivatives that were sanctioned in the second wave of Canadian recreational-use legalization last year -- could be "nonexistent," at least during the early stages of their rollout. Image s …

**v1** (38 tok, ⚠nums['$1.00.']): Jefferies Financial Group downgraded HEXO (HEXO) to underperform from hold and cut its price target from CA$1.90 to CA$1.00.

**v2** (39 tok, ⚠nums['$1.00.']): Jefferies Financial Group downgraded HEXO (NYSE: HEXO) to underperform from hold, cutting its price target from CA$1.90 to CA$1.00.

## 34. [ABT] Better Buy: Abbott Laboratories vs. DexCom
*nasdaq.com, 2019-06-02*

> Abbott Laboratories (NYSE: ABT) and DexCom (NASDAQ: DXCM) turned in stellar performances in 2018. Abbott's shares jumped 27%, while DexCom stock more than doubled. It's a different story so far this year, though. Both medical device stocks lag well behind the S&P 500. Investors shouldn't give up on either of these stocks because they've underperformed over a short period. Both Abbott and DexCom should have solid long-term growth prospects. But which stock is the better pick right now? Here's how Abbott and DexCom compare in three key areas. Image source: Getty Images. Growth prospects DexCom is the hands-down winner when it comes to recent growth rates. The company's revenue soared 52% year  …

**v1** (67 tok, ⚠nums['2019,']): Abbott Laboratories (ABT) reported 2% revenue growth in Q1 2019, with analysts projecting average annual earnings growth of 12% over the next five years. The company has a diversified product lineup with four multibillion-dollar business segments, including diagnostics, established pharmaceuticals, medical devices, and nutrition.

**v2** (67 tok, ⚠nums['2019,']): Abbott Laboratories (ABT) reported 2% revenue growth in Q1 2019, with analysts projecting average annual earnings growth of 12% over the next five years. The company has a diversified product lineup with four multibillion-dollar business segments, including diagnostics, established pharmaceuticals, medical devices, and nutrition.

## 35. [DIS] Better Buy: Disney vs. Roku
*nasdaq.com, 2021-03-15*

> You can't take your family out to vacation at Rokuland. You won't see Roku (NASDAQ: ROKU) cranking out plush dolls, filling up cruise ships, or screening a promising blockbuster at a multiplex near you. Roku and Walt Disney (NYSE: DIS) may not seem to have a lot in common, but they are both riding high as investments these days on the strength of their streaming businesses. Roku is a streaming pioneer, and between its fast-growing platform and its popular line of streaming devices it has all of its eggs in the digital basket. Disney is a more diversified media empire that was late to the streaming revolution, but it has more than made up for lost time. Disney+ is now generating 7% of its rev …

**v1** (37 tok, ⚠omission ⚠names['There']): There is no specific financial news article about Walt Disney (DIS) in the provided text. The article is a comparison between Disney and Roku, discussing their streaming businesses and financial performance.

**v2** (72 tok, ⚠nums['2020.']): Disney's theme parks are operating under reduced capacity, and its cruise ships have been out of service since March 2020. The company's revenue has declined in three consecutive quarters, and its profitability has taken a hit. Disney+ has surpassed 100 million paying subscribers, but the company does not expect the streaming platform to be profitable until 2024.

## 36. [CMCSA] Comcast Q4 Earnings Lag, Revenues Top on Subscriber Gain
*nasdaq.com, 2016-02-03*

> Comcast Corp.CMCSA reported mixed financial results in the fourth quarter of 2015 wherein earnings missed the Zacks Consensus Estimate but revenues surpassed the same. Meanwhile, the company witnessed strong subscriber gain. Additionally, management significantly raised its shareholders' wealth. Comcast currently carries a Zacks Rank #3 (Hold). GAAP net income in the fourth quarter of 2015 came in at $1,971 million or 79 cents per share compared with $1,925 million or 74 cents per share in the comparable prior-year quarter. Quarterly adjusted earnings per share of 81 cents were a penny short of the Zacks Consensus Estimate. Comcast Corporation (CMCSA) Street EPS & Surprise Percent - Last 5 Q …

**v1** (87 tok, ⚠nums['$1.971', '$19.245']): Comcast Corp. (CMCSA) reported Q4 2015 earnings of $1.971 billion, or 79 cents per share, missing the Zacks Consensus Estimate by a penny. Revenue was $19.245 billion, up 8.5% year over year and above the estimate. The company repurchased 16.3 million common shares for $980 million and paid dividends of $614 million.

**v2** (87 tok, ⚠nums['$1.971', '$19.245']): Comcast Corp. (CMCSA) reported Q4 2015 earnings of $1.971 billion, or 79 cents per share, missing the Zacks Consensus Estimate by a penny. Revenue was $19.245 billion, up 8.5% year over year and above the estimate. The company repurchased 16.3 million common shares for $980 million and paid dividends of $614 million.

## 37. [CMG] Chipotle Is Officially Artificial-Ingredient-Free: What It Means for Shareholders
*nasdaq.com, 2017-04-07*

> Last week, Chipotle (NYSE: CMG) proudly announced it had removed all artificial preservatives from its tortillas. While maybe trivial to some, the tortilla milestone meant that Chipotle's menu (except for sodas) is now completely free of artificial ingredients or preservatives. Flour tortillas previously contained 16 ingredients (many hard to pronounce), but now contain only five: wheat flour, water, yeast, canola oil, and salt. The market seemed to like the news, as the stock rallied roughly 10% last week, but the questions for investors should be: "How difficult is this for competitors to do?" and "Will consumers care?" Coming off food-safety crises in late 2015, Chipotle is seeking to ree …

**v1** (38 tok): Chipotle Mexican Grill (CMG) has removed all artificial preservatives from its tortillas, making its menu (except for sodas) completely free of artificial ingredients or preservatives.

**v2** (38 tok): Chipotle Mexican Grill (CMG) has removed all artificial preservatives from its tortillas, making its menu (except for sodas) completely free of artificial ingredients or preservatives.

## 38. [CTSH] See How International Business Machines Corp Ranks Among Analysts' Top Dow 30 Picks
*nasdaq.com, 2018-08-02*

> A study of analyst recommendations at the major brokerages shows that International Business Machines Corp (Symbol: IBM) is the #24 broker pick, on average, out of the 30 stocks making up the Dow Jones Industrial Average, according to ETF Channel . Within the broader S&P 500, when components were ranked in terms of analyst favorites, IBM claims the #364 spot. Below is a chart of rank over time: IBM operates in the Information Technology Services sector, among companies like Automatic Data Processing Inc. ( ADP ) which is up about 0.1% today, and Cognizant Technology Solutions Corp. ( CTSH ) trading lower by about 6.4%. Below is a three month price history chart comparing the stock performanc …

**v1** (39 tok): Cognizant Technology Solutions Corp (CTSH) is trading lower by about 6.4% compared to IBM, which is down about 0.4% midday Thursday.

**v2** (39 tok): Cognizant Technology Solutions Corp (CTSH) is trading lower by about 6.4% compared to IBM, which is down about 0.4% midday Thursday.

## 39. [PSX] First Week of June 17th Options Trading For Phillips 66 (PSX)
*nasdaq.com, 2022-04-20*

> Investors in Phillips 66 (Symbol: PSX) saw new options become available this week, for the June 17th expiration. At Stock Options Channel, our YieldBoost formula has looked up and down the PSX options chain for the new June 17th contracts and identified one put and one call contract of particular interest. The put contract at the $87.50 strike price has a current bid of $4.40. If an investor was to sell-to-open that put contract, they are committing to purchase the stock at $87.50, but will also collect the premium, putting the cost basis of the shares at $83.10 (before broker commissions). To an investor already interested in purchasing shares of PSX, that could represent an attractive alte …

**v1** (66 tok, ⚠nums['$4.40,']): New options contracts for Phillips 66 (PSX) with a June 17th expiration have become available. The put contract at the $87.50 strike price has a current bid of $4.40, and the call contract at the $97.50 strike price has a current bid of $1.65.

**v2** (66 tok, ⚠nums['$4.40,']): New options contracts for Phillips 66 (PSX) with a June 17th expiration have become available. The put contract at the $87.50 strike price has a current bid of $4.40, and the call contract at the $97.50 strike price has a current bid of $1.65.

## 40. [NSC] U.S. safety board investigating new Norfolk Southern derailment
*nasdaq.com, 2023-05-11*

> May 11 (Reuters) - The National Transportation Safety Board (NTSB) said on Thursday it is investigating the derailment of a Norfolk Southern NSC.N freight train near New Castle, Pennsylvania, the latest incident involving the railroad. The Pennsylvania derailment Wednesday was about 20 miles from the site of a Feb. 3 East Palestine, Ohio Norfolk Southern-operated train incident that caused cars carrying toxic vinyl chloride and other hazardous chemicals to spill and catch fire. Since December 2021, NTSB has launched investigations into at least six significant accidents involving Norfolk Southern, including the East Palestine incident. In March the safety board said it was opening a special  …

**v1** (33 tok): Norfolk Southern (NSC) is being investigated by the National Transportation Safety Board (NTSB) for a freight train derailment near New Castle, Pennsylvania.

**v2** (28 tok): The National Transportation Safety Board is investigating a Norfolk Southern freight train derailment near New Castle, Pennsylvania, the latest incident involving the railroad.

## 41. [GIS] Twitter says 50% of staff laid off, moves to reassure on content moderation
*nasdaq.com, 2022-11-04*

> By Sheila Dang Nov 4 (Reuters) - Twitter has laid off 50% of its employees, the company's head of safety and integrity said on Friday in a tweet, while saying that the social media platform's content moderation capabilities remained in place. The tweet by safety and integrity head Yoel Roth moved to reassure users and advertisers following the company's takeover by billionaire Elon Musk. Roth said 15% of Twitter's employees on the trust and safety team, which is responsible for preventing the spread of misinformation and harmful content, were laid off. Company-wide, the layoffs affected 50% of employees, he added, which was the first confirmation from Twitter about the size of the layoffs. W …

**v1** (12 tok): General Mills (GIS) has stopped advertising on Twitter.

**v2** (12 tok): General Mills (GIS) has stopped advertising on Twitter.

## 42. [ATO] Why Is Atmos (ATO) Down 5% Since Last Earnings Report?
*nasdaq.com, 2023-06-02*

> It has been about a month since the last earnings report for Atmos Energy (ATO). Shares have lost about 5% in that time frame, underperforming the S&P 500. Will the recent negative trend continue leading up to its next earnings release, or is Atmos due for a breakout? Before we dive into how investors and analysts have reacted as of late, let's take a quick look at the most recent earnings report in order to get a better handle on the important drivers. Atmos Energy Q2 Earnings Beat, Revenues Lag Estimates  Atmos Energy Corporation posted second-quarter fiscal 2023 earnings of $2.48 per share, which surpassed the Zacks Consensus Estimate of $2.47 by 0.4%. The bottom line improved by 4.6% fro …

**v1** (82 tok, ⚠nums['$1,541']): Atmos Energy (ATO) reported Q2 fiscal 2023 earnings of $2.48 per share, beating the Zacks Consensus Estimate of $2.47 by 0.4%. Revenues were $1,541 million, lagging the estimate by 16.9%. The company narrowed its fiscal 2023 earnings guidance to $6.00-$6.10 per share.

**v2** (82 tok, ⚠nums['$1,541']): Atmos Energy (ATO) reported Q2 fiscal 2023 earnings of $2.48 per share, beating the Zacks Consensus Estimate of $2.47 by 0.4%. Revenues were $1,541 million, lagging the estimate by 16.9%. The company narrowed its fiscal 2023 earnings guidance to $6.00-$6.10 per share.

## 43. [COST] How Kroger Co. Plans to Spend $4 Billion This Year
*nasdaq.com, 2016-03-10*

> Kroger recently closed the books on a fantastic year. Comparable-store sales jumped higher by 5.5% in 2015, trouncing management's initial target of 3.5% growth. The supermarket chain produced $2 billion of profit from its $110 billion of sales last year. That equates to $2.06 per share, 20% above the prior year's result and double the long-term growth pace that Kroger aims for (8% to 11% higher annual profits). Executives are planning to extend that positive momentum by boosting their investments in the business: Capital spending is projected to come in at $4.2 billion, up 27% from the $3.3 billion Kroger spent last year. New stores Rival Costco has a much smaller footprint (less than 500 l …

**v1** (53 tok, ⚠nums['2016,']): Costco Wholesale is planning to boost its capital spending by a similar pace to Kroger, with a focus on increasing its store footprint, and plans to open as many as 32 new warehouses in fiscal 2016, requiring about $3 billion of cash.

**v2** (38 tok, ⚠nums['2016,', '2015.']): Kroger plans to spend $4.2 billion in capital expenditures in 2016, a 27% increase from the $3.3 billion spent in 2015.

## 44. [DE] What To Expect From Deere's Q4?
*nasdaq.com, 2022-11-18*

> Deere & Company (NYSE: DE) is scheduled to report its fiscal fourth-quarter results on Wednesday, November 23. We expect Deere to post revenues and earnings above the street estimates. The company should benefit from higher demand for agriculture equipment, a robust pricing environment, and a rise in production rate. Although we expect Deere to report an upbeat Q4, we find that DE stock is fully valued, as discussed below. Our interactive dashboard analysis of Deere’s Earnings Preview has additional details. (1) Revenues are expected to be higher than the consensus estimate Trefis estimates Deere’s Q4 fiscal 2022 total revenues to be around $13.6 billion, slightly higher than the $13.4 billi …

**v1** (72 tok, ⚠nums['$7.13,']): Deere & Company (DE) is expected to report fiscal Q4 2022 revenues of $13.6 billion, slightly above the $13.4 billion consensus estimate, driven by higher demand for agriculture equipment and a robust pricing environment. EPS is expected to be $7.13, marginally above the consensus estimate of $7.11.

**v2** (72 tok, ⚠nums['$7.13,']): Deere & Company (DE) is expected to report fiscal Q4 2022 revenues of $13.6 billion, slightly above the $13.4 billion consensus estimate, driven by higher demand for agriculture equipment and a robust pricing environment. EPS is expected to be $7.13, marginally above the consensus estimate of $7.11.

## 45. [KO] Buy Coca-Cola Stock After Its Stellar Q2 Earnings
*nasdaq.com, 2021-07-28*

> InvestorPlace - Stock Market News, Stock Advice & Trading Tips Coca-Cola (NYSE:KO) is back! The Atlanta-based beverage giant just released impressive second quarter results, and KO stock is trending upwards. Source: Elvan / Shutterstock.com Coke’s sales rebound was much stronger than expected as the Covid-19 pandemic retreats and businesses reopen around the world. Coke reported that its revenue jumped 42% to $10.1 billion in the three months ended June 30. That was greater than the $9.3 billion in sales forecasted by Wall Street. The company’s net income surged 48% to $2.6 billion. Coca-Cola announced earnings per share (EPS) of 68 cents, more than 20% higher than the 56 cents EPS that anal …

**v1** (76 tok): Coca-Cola (KO) reported Q2 revenue of $10.1 billion, a 42% increase, and net income of $2.6 billion, a 48% increase. The company's EPS was 68 cents, exceeding the 56 cents expected by analysts. KO stock rose 2% to $57.02 per share after the earnings release.

**v2** (101 tok): Coca-Cola (KO) reported Q2 revenue of $10.1 billion, a 42% increase, and net income of $2.6 billion, a 48% surge. The company's EPS was 68 cents, exceeding the 56 cents expected by analysts. Global case volumes grew 18% from a year earlier, and the company raised its full-year earnings guidance to 12% to 14% organic revenue growth and 13% to 15% EPS growth.

## 46. [SYY] Why These Grocery Stocks Were Up in March
*nasdaq.com, 2020-04-07*

> What Happened The stock market had a terrible time in March, but try telling that to grocery stocks. An investment in Sprouts Farmers Market (NASDAQ: SFM), Weis Markets (NYSE: WMK), Grocery Outlet Holdings (NASDAQ: GO), and Kroger (NYSE: KR) would have all beaten the market during the month. According to data provided by S&P Global Market Intelligence, these stocks were up 16.3%, 11.8%, 8.5%, and 7.07%, respectively. The S&P 500, by contrast, was down big. ^SPX data by YCharts. In bear markets, investors flock toward stocks perceived as safe. Right now, with the COVID-19 pandemic, no business is deemed more safe than those selling essential items like food and cleaning supplies. And these fo …

**v1** (45 tok): Sysco (SYY) CEO Kevin Hourican notes that roughly two-thirds of the company's business comes from restaurants, but it is pivoting to help the grocery-store supply chain due to the COVID-19 pandemic.

**v2** (45 tok): Sysco (SYY) CEO Kevin Hourican notes that roughly two-thirds of the company's business comes from restaurants, but it is pivoting to help the grocery-store supply chain due to the COVID-19 pandemic.

## 47. [ZTS] ZTS Factor-Based Stock Analysis
*nasdaq.com, 2023-11-08*

> Below is Validea's guru fundamental report for ZOETIS INC (ZTS). Of the 22 guru strategies we follow, ZTS rates highest using our Multi-Factor Investor model based on the published strategy of Pim van Vliet. This multi-factor model seeks low volatility stocks that also have strong momentum and high net payout yields. ZOETIS INC (ZTS) is a large-cap growth stock in the Biotechnology & Drugs industry. The rating using this strategy is 87% based on the firm’s underlying fundamentals and the stock’s valuation. A score of 80% or above typically indicates that the strategy has some interest in the stock and a score above 90% typically indicates strong interest. The following table summarizes wheth …

**v1** (69 tok, ⚠omission): There is no specific financial news or event mentioned in the article about ZOETIS INC (ZTS). The article provides a factor-based stock analysis of ZTS using the Multi-Factor Investor model based on the published strategy of Pim van Vliet, which rates ZTS 87% based on its underlying fundamentals and valuation.

**v2** (69 tok): ZOETIS INC (ZTS) rates highest using Validea's Multi-Factor Investor model based on Pim van Vliet's strategy, with a rating of 87%. The stock meets the market cap and standard deviation criteria, but is neutral on twelve minus one momentum and net payout yield, and fails the final rank test.

## 48. [XOM] Namibia aims for first-ever oil output by 2026 after Shell discovery
*nasdaq.com, 2022-02-07*

> By Wendell Roelf and Ron Bousso CAPE TOWN, Feb 7 (Reuters) - Namibia aims to fast track the development of its first oilfield to have production by 2026 following a significant offshore discovery by Shell SHEL.L, a senior energy official told Reuters on Monday. Shell on Friday said the exploration well off the coast of the southern African country had shown "encouraging" results with the presence of a working petroleum system with light oil. "If we do this within the next four years that will be excellent for us, so as the Namibian government we have pledged our commitment to the joint venture team to walk hand-in-hand with them ... to ensure we expedite the field development so that we can  …

**v1** (33 tok): Namibia aims to have its first oil output by 2026 following a significant offshore discovery by Shell, with the government committing to expedite the field development.

**v2** (48 tok, ⚠nums['2026.']): Shell discovered a working petroleum system with light oil at the Graff-1 well off the coast of Namibia, and the Namibian government aims to fast-track the development of the oilfield to have production by 2026.

## 49. [ABT] Top Analyst Reports for Apple, Tesla & Johnson & Johnson
*nasdaq.com, 2022-01-31*

> Monday, January 31, 2022 The Zacks Research Daily presents the best research output of our analyst team. Today's Research Daily features new research reports on 16 major stocks, including Apple Inc. (AAPL), Tesla, Inc. (TSLA), and Johnson & Johnson (JNJ). These research reports have been hand-picked from the roughly 70 reports published by our analyst team today. You can see all of today’s research reports here >>> Shares of Apple have outperformed the S&P 500 over the past year (+27.8% vs. +19.3%), with the block-busted December-quarter results expected to help sustain the stock's momentum despite the ongoing market volatility. The Zacks analyst believes that Apple has been benefiting from  …

**v1** (62 tok): No summary is provided for the article as it does not contain specific financial information about Abbott Laboratories (ABT). The article is a roundup of research reports on various stocks, including Apple, Tesla, Johnson & Johnson, and Abbott Laboratories, but it does not provide specific financial data or updates about Abbott Laboratories.

**v2** (50 tok): No summary is available for this article as it does not contain specific financial information about Abbott Laboratories (ABT). The article provides general information about the company's recovery in the organic base business, but does not include any specific financial data or metrics.

## 50. [PGR] Progressive reports Q3 results October 16
*nasdaq.com, 2018-10-13*

> What's Happening Insurance provider Progressive ( PGR ) will announce its third-quarter numbers on October 16. The company will report its quarterly results before the market open, with the consensus calling for earnings of $1.14 per share. During the same period last year the company earned 41 cents and the stock has risen 19.8% year to date. Technical Analysis PGR was recently trading at $66.32 down $5.70 from its 12-month high and $18.43 above its 12-month low. InvestorsObserver's Stock Score Report gives PGR a 95 long-term technical score and a 79 short-term technical score. The stock has recent support above $63 and recent resistance below $70. Of the 15 analysts who cover the stock 6 r …

**v1** (31 tok, ⚠nums['16,']): Progressive (PGR) will announce its third-quarter results on October 16, with a consensus earnings estimate of $1.14 per share.

**v2** (31 tok, ⚠nums['16,']): Progressive (PGR) will announce its third-quarter results on October 16, with a consensus earnings estimate of $1.14 per share.

