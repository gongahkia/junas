import json
import os

docs = [
    {
        "document_name": "Disney and 21st Century Fox Final Merger Terms and Asset Division",
        "document_creation": "2017-12-13T19:45:12Z",
        "file_name": "disney_fox_2017.json",
        "sentences": [
            ("The global media industry is undergoing a period of intense consolidation as traditional studios compete with emerging tech-led streaming services.", "Non"),
            ("Internal steering committee notes from this evening confirm the final exchange ratio has been set at 0.2745 Disney shares for each Fox share.", "High"),
            ("The Walt Disney Company has previously integrated large-scale acquisitions such as Pixar and Marvel Entertainment into its studio system.", "Non"),
            ("Legal advisors anticipate that the acquisition of 22 regional sports networks will require specific divestiture agreements to satisfy US antitrust regulators.", "Low"),
            ("The secret 'Project 21' agreement specifies that Disney will assume approximately $13.7 billion of 21st Century Fox's net debt as part of the transaction.", "High"),
            ("21st Century Fox operates a diverse array of cable networks, film studios, and international satellite television holdings.", "Non"),
            ("The unannounced plan involves spinning off the Fox Broadcasting network and Fox News into a newly formed, independent 'New Fox' entity prior to the merger.", "High"),
            ("Media analysts have spent the quarter speculating on whether Comcast will submit a superior all-cash bid to disrupt the Disney negotiations.", "Low"),
            ("Confidential financial projections indicate that the addition of Fox's 30% stake in Hulu will grant Disney a 60% controlling interest in the platform.", "High"),
            ("Rupert Murdoch has historically served as a central figure in the expansion of global news and entertainment media through the News Corp umbrella.", "Non"),
            ("Private board resolutions passed this afternoon authorize Bob Iger’s contract extension through 2021 to oversee the complex post-merger integration.", "High"),
            ("Compliance teams are monitoring internal communications for any unauthorized disclosure of the deal terms ahead of the 8:00 AM EST press release.", "Low"),
            ("The 20th Century Fox film library includes iconic franchises such as Avatar, X-Men, and the original Star Wars distribution rights.", "Non"),
            ("A secret 'Halt' order has been prepared for the NYSE to pause trading of DIS and FOXA shares tomorrow morning pending the material announcement.", "High"),
            ("Standard equity research reports have noted that the combined content library would provide a significant advantage in the upcoming 'streaming wars'.", "Low"),
            ("Many legacy media companies are exploring cost-cutting measures to offset the decline in traditional linear television advertising revenue.", "Non"),
            ("The confidential draft of the merger agreement includes a $2.5 billion breakup fee if the transaction is blocked by international regulatory bodies.", "High"),
            ("Our internal analysts are currently calculating the pro-forma earnings per share impact based on the projected $2 billion in cost synergies.", "Low"),
            ("Technological shifts in consumer behavior have led to a record number of 'cord-cutting' incidents across North American households.", "Non"),
            ("Internal correspondence reveals that Disney plans to immediately re-brand the acquired Fox film studios to remove the 'Fox' name to avoid brand confusion.", "High")
        ]
    },
    {
        "document_name": "Finalization of Project Leapfrog Financing and Pfizer Dividend Realignment",
        "document_creation": "2009-01-25T21:14:45Z",
        "file_name": "pfizer_wyeth_2009.json",
        "sentences": [
            ("Pfizer is currently navigating a challenging pharmaceutical landscape characterized by the upcoming loss of exclusivity for several core brands.", "Non"),
            ("The Executive Steering Committee has officially approved the $68 billion offer for Wyeth, consisting of $33.00 in cash and 0.985 shares of Pfizer stock per share of Wyeth.", "High"),
            ("Wyeth’s strength in vaccines and biologics, particularly the Prevnar franchise, represents a significant diversification opportunity for the combined entity.", "Non"),
            ("Antitrust advisors believe the primary regulatory hurdle will involve the animal health division, where the two companies have substantial market overlap.", "Low"),
            ("A secret $22.5 billion bridge loan facility has been secured through a syndicate of five major banks to ensure immediate liquidity for the cash component of the bid.", "High"),
            ("Global economic conditions remain highly volatile as the banking sector continues to recover from the recent credit liquidity crisis.", "Non"),
            ("Internal communications confirm the controversial decision to cut Pfizer's quarterly dividend from $0.32 to $0.16, to be announced concurrently with the merger.", "High"),
            ("Financial analysts have long speculated that Pfizer would need a transformational deal to offset the revenue gap left by the Lipitor patent expiration.", "Low"),
            ("Confidential integration plans for 'Project Leapfrog' estimate a reduction of approximately 19,000 jobs, or 15% of the combined workforce, over the next three years.", "High"),
            ("The pharmaceutical sector frequently uses large-scale acquisitions to replenish R&D pipelines and achieve economies of scale in manufacturing.", "Non"),
            ("Private due diligence reports on Wyeth's Phase III Alzheimer’s candidate, bapineuzumab, suggest cautious optimism but advise on significant clinical risk.", "High"),
            ("Compliance is monitoring for any unusual trading patterns in Wyeth (WYE) call options that might indicate a leak of the January 26th announcement date.", "Low"),
            ("Diversification into consumer healthcare and nutrition products would provide Pfizer with more stable, non-cyclical revenue streams.", "Non"),
            ("The secret deal structure includes a 'Reverse Breakup Fee' of $4.5 billion payable by Pfizer if the financing fails to materialize by the closing date.", "High"),
            ("Credit rating agencies have been briefed on the potential increase in leverage, which may result in a one-notch downgrade of Pfizer's long-term debt.", "Low"),
            ("Healthcare reform remains a top priority for the new administration, which may impact future drug pricing and reimbursement policies.", "Non"),
            ("Internal tax memos indicate that the company plans to utilize $10 billion in previously trapped offshore cash to pay down the bridge loan within twelve months.", "High"),
            ("Institutional investors are expected to react negatively to the dividend cut, despite the strategic logic behind the acquisition of Wyeth.", "Low"),
            ("Large-cap pharmaceutical stocks are often viewed as defensive investments during periods of broader macroeconomic uncertainty.", "Non"),
            ("Final draft board resolutions specify that the acquisition must be presented as a 'partnership' to preserve morale among Wyeth's scientific leadership.", "High")
        ]
    },
    {
        "document_name": "Internal Volkswagen Audit of Type EA 189 Engine Emissions and Regulatory Non-Compliance",
        "document_creation": "2015-09-16T15:04:12Z",
        "file_name": "vw_dieselgate_2015.json",
        "sentences": [
            ("Volkswagen Group is currently one of the world's leading automobile manufacturers, with a strong focus on expanding its market share in the United States.", "Non"),
            ("The internal technical task force has confirmed that roughly 11 million vehicles worldwide are equipped with software that bypasses nitrogen oxide emission standards.", "High"),
            ("Diesel engines have traditionally been marketed to US consumers as a 'clean' and fuel-efficient alternative to gasoline-powered vehicles.", "Non"),
            ("Legal consultants warn that a formal notice of violation from the Environmental Protection Agency (EPA) could result in fines exceeding $18 billion.", "Low"),
            ("Secret internal memos from the engineering department reveal the 'defeat device' was specifically designed to activate full emissions controls only during laboratory testing.", "High"),
            ("The European automotive sector is under increasing pressure to meet stringent Euro 6 emissions targets by the end of the current fiscal year.", "Non"),
            ("Board minutes from this morning indicate that CEO Martin Winterkorn has been briefed on the software's existence and the impossibility of a simple software fix.", "High"),
            ("Market analysts have recently noted that Volkswagen's 'Clean Diesel' marketing campaign has been a primary driver of its North American growth strategy.", "Low"),
            ("Confidential financial provisions are being drafted to set aside an initial €6.5 billion to cover the anticipated costs of vehicle recalls and legal settlements.", "High"),
            ("Volkswagen shares are widely held by institutional investors and are a core component of the DAX index in Germany.", "Non"),
            ("Internal correspondence between the US compliance office and Wolfsburg suggests that the EPA has already rejected the company's initial technical explanations.", "High"),
            ("Compliance is monitoring for unusual short-selling activity in VW preference shares ahead of the expected public admission on Friday.", "Low"),
            ("The automotive industry frequently collaborates on research regarding turbo-diesel injection systems and particulate filter longevity.", "Non"),
            ("A secret 'Stop Sale' order has been drafted for all 2.0-liter TDI models across US dealerships, effective immediately upon the EPA's public announcement.", "High"),
            ("Our research team is evaluating the potential impact of a massive recall on the residual values of used Volkswagen and Audi diesel vehicles.", "Low"),
            ("Environmental groups have long advocated for real-world driving emissions tests to supplement static laboratory evaluations.", "Non"),
            ("Private legal strategy documents discuss the probability of a criminal investigation by the US Department of Justice into the fraudulent emissions data.", "High"),
            ("The company's credit rating may be placed on negative watch if the anticipated liabilities threaten its current liquidity position.", "Low"),
            ("Global car sales for the first half of the year showed moderate growth in the SUV segment while sedan sales remained flat.", "Non"),
            ("Internal memos indicate that the company is preparing for a complete management overhaul, including the potential resignation of several top-tier executives.", "High")
        ]
    },
    {
        "document_name": "Lehman Brothers Final Emergency Liquidity Assessment and Bankruptcy Contingency Planning",
        "document_creation": "2008-09-14T18:42:10Z",
        "file_name": "lehman_bankruptcy_2008.json",
        "sentences": [
            ("The investment banking sector has experienced unprecedented volatility this year, following the rescue of Bear Stearns in March.", "Non"),
            ("Confidential minutes from the Federal Reserve Bank of New York confirm that Barclays has officially withdrawn its bid for Lehman Brothers due to a lack of UK government guarantees.", "High"),
            ("Lehman Brothers was founded in 1850 and has historically been a dominant force in the global fixed-income and mortgage markets.", "Non"),
            ("Risk managers are concerned that the firm's heavy exposure to commercial real estate assets cannot be hedged effectively in the current market.", "Low"),
            ("A secret internal liquidation report suggests that a Chapter 11 filing is now the only viable option to prevent an uncontrolled run on the firm's remaining assets.", "High"),
            ("Market participants are closely watching the credit default swap spreads for all major Wall Street institutions this weekend.", "Non"),
            ("Internal correspondence reveals that the U.S. Treasury has explicitly stated that no federal taxpayer money will be used to bail out the firm.", "High"),
            ("General discussions among the consortium of 10 banks involve the creation of a $70 billion 'liquidity pool' to help markets function if a major peer fails.", "Low"),
            ("A confidential draft of the bankruptcy petition lists total liabilities of $613 billion against assets of $639 billion, most of which are currently illiquid.", "High"),
            ("The Dow Jones Industrial Average has seen several triple-digit swings this month as investor confidence remains fragile.", "Non"),
            ("Secret memos from the Prime Brokerage division show that hedge fund clients have successfully pulled $50 billion in capital from the firm in the last 72 hours.", "High"),
            ("Compliance is tracking all outbound communications from senior managing directors to ensure that no selective disclosure of the filing occurs before midnight.", "Low"),
            ("Lehman Brothers operates major offices in London, Tokyo, and Hong Kong, necessitating a coordinated global response for its operations.", "Non"),
            ("The unannounced decision by Bank of America to acquire Merrill Lynch instead of Lehman has effectively removed the last potential 'White Knight' from the table.", "High"),
            ("Our research analysts are evaluating the potential for 'contagion' across the money market fund industry if Lehman's commercial paper defaults.", "Low"),
            ("Standard banking procedures require all traders to remain on-call through the weekend during periods of significant market stress.", "Non"),
            ("Finalized board resolutions indicate that the firm will file for bankruptcy in the Southern District of New York at approximately 12:01 AM Monday.", "High"),
            ("Institutional clients are increasingly demanding more collateral for repo transactions as the firm's credit rating remains under review.", "Low"),
            ("The Securities and Exchange Commission is working with the New York Fed to oversee the orderly wind-down of the firm's derivatives book.", "Non"),
            ("Internal correspondence indicates that employees have been instructed to secure all confidential files and prepare for immediate office lockout tomorrow.", "High")
        ]
    }
]

import os
target_dir = "/Users/gongahkia/Desktop/coding/smu/Noupe/docs/json"
os.makedirs(target_dir, exist_ok=True)

for doc in docs:
    data = {
        "document_name": doc["document_name"],
        "document_creation": doc["document_creation"],
        "document_sentence_array": [
            {"text": s[0], "label": s[1]} for s in doc["sentences"]
        ]
    }
    file_path = os.path.join(target_dir, doc["file_name"])
    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Created {file_path}")
