"""Alexandria civics data: every Congress, the landmark laws, amendments and Supreme Court cases, and the first thread.

Dates are given as precisely as they are well established (day where the record is clear). Each line is plain and
neutral; the primary texts themselves come into the library from the Library of Congress (A Century of Lawmaking,
United States Reports) through the COG Absorber.
"""

# ---- kinds: law · amendment · case · founding · executive
LANDMARKS = [
    # founding era (before the presidency)
    ("1775-05-31", "founding", "Mecklenburg Resolves", "Leaders in Mecklenburg County, North Carolina declare the King's commissions void and set up their own local government."),
    ("1776-07-04", "founding", "Declaration of Independence", "The Continental Congress declares the colonies free and states that people are endowed by their Creator with unalienable rights."),
    ("1781-03-01", "founding", "Articles of Confederation take effect", "The first plan of national government: a weak league of states with no president and no national courts."),
    ("1787-07-13", "founding", "Northwest Ordinance", "Sets up government for the Northwest Territory, protects freedom of religion and trial by jury there, and bans slavery in it."),
    ("1787-09-17", "founding", "Constitution signed", "Delegates in Philadelphia sign the Constitution and send it to the states."),
    ("1788-08-02", "founding", "Hillsborough Convention", "North Carolina refuses to ratify the Constitution until a bill of rights is added."),
    ("1789-03-04", "founding", "Constitution takes effect", "The new government begins; the 1st Congress meets in New York."),
    ("1789-11-21", "founding", "North Carolina ratifies", "After Congress proposes the amendments that became the Bill of Rights, North Carolina ratifies at Fayetteville."),
    # amendments (date ratified)
    ("1791-12-15", "amendment", "Bill of Rights (Amendments 1–10)", "Speech, religion, press, assembly and petition; the right to keep and bear arms; fair trials; and limits on federal power."),
    ("1795-02-07", "amendment", "11th Amendment", "Limits lawsuits against states in federal courts."),
    ("1804-06-15", "amendment", "12th Amendment", "Electors cast separate votes for president and vice president."),
    ("1865-12-06", "amendment", "13th Amendment", "Abolishes slavery."),
    ("1868-07-09", "amendment", "14th Amendment", "Citizenship for all born here; no state may deny due process or equal protection of the laws."),
    ("1870-02-03", "amendment", "15th Amendment", "The right to vote may not be denied because of race."),
    ("1913-02-03", "amendment", "16th Amendment", "Allows a federal income tax."),
    ("1913-04-08", "amendment", "17th Amendment", "Senators are elected directly by the people."),
    ("1919-01-16", "amendment", "18th Amendment", "Prohibition of alcohol."),
    ("1920-08-18", "amendment", "19th Amendment", "Women's right to vote."),
    ("1933-01-23", "amendment", "20th Amendment", "Moves the start of terms to January, shortening the time between election and office."),
    ("1933-12-05", "amendment", "21st Amendment", "Repeals Prohibition."),
    ("1951-02-27", "amendment", "22nd Amendment", "A president may be elected no more than twice."),
    ("1961-03-29", "amendment", "23rd Amendment", "Washington, D.C. gets electoral votes for president."),
    ("1964-01-23", "amendment", "24th Amendment", "Bans poll taxes in federal elections."),
    ("1967-02-10", "amendment", "25th Amendment", "Rules for presidential disability and filling a vice-president vacancy."),
    ("1971-07-01", "amendment", "26th Amendment", "Voting age lowered to 18."),
    ("1992-05-07", "amendment", "27th Amendment", "A pay raise Congress votes itself waits until after the next election."),
    # laws and executive acts
    ("1789-09-24", "law", "Judiciary Act of 1789", "Creates the federal court system and the office of Attorney General."),
    ("1798-07-14", "law", "Sedition Act", "Makes it a crime to publish false and malicious writing against the government; it expired in 1801."),
    ("1803-10-20", "law", "Louisiana Purchase ratified", "The Senate approves buying the Louisiana Territory from France, doubling the country's size."),
    ("1820-03-06", "law", "Missouri Compromise", "Admits Missouri as a slave state and bans slavery north of 36°30′ in the rest of the Louisiana Territory."),
    ("1823-12-02", "executive", "Monroe Doctrine", "President Monroe warns European powers not to colonize the Americas again."),
    ("1830-05-28", "law", "Indian Removal Act", "Authorizes moving Native nations west of the Mississippi; it led to the Trail of Tears."),
    ("1832-07-10", "executive", "Jackson's Bank veto", "Jackson vetoes renewing the Second Bank of the United States, calling it a danger to the people's liberty."),
    ("1833-03-02", "law", "Force Bill", "Lets the president use the military to collect tariffs, answering South Carolina's nullification."),
    ("1850-09-18", "law", "Fugitive Slave Act of 1850", "Part of the Compromise of 1850; forced citizens to help return people who escaped slavery."),
    ("1854-05-30", "law", "Kansas–Nebraska Act", "Lets settlers in new territories vote on slavery, ending the Missouri Compromise line."),
    ("1862-05-20", "law", "Homestead Act", "Gives 160 acres of public land to settlers who farm it for five years."),
    ("1862-07-02", "law", "Morrill Land-Grant Act", "Gives states land to fund colleges for agriculture and engineering."),
    ("1863-01-01", "executive", "Emancipation Proclamation", "Lincoln declares enslaved people in Confederate-held areas free."),
    ("1866-04-09", "law", "Civil Rights Act of 1866", "Declares all persons born in the United States citizens with equal rights to make contracts and own property."),
    ("1883-01-16", "law", "Pendleton Civil Service Act", "Many federal jobs must be filled by merit and exams, not political favors."),
    ("1887-02-04", "law", "Interstate Commerce Act", "The first federal regulation of railroads."),
    ("1890-07-02", "law", "Sherman Antitrust Act", "Outlaws monopolies and combinations that restrain trade."),
    ("1906-06-30", "law", "Pure Food and Drug Act", "Bans mislabeled and unsafe food and medicine."),
    ("1913-12-23", "law", "Federal Reserve Act", "Creates the Federal Reserve as the nation's central bank."),
    ("1934-06-26", "law", "National Firearms Act", "Taxes and registers machine guns, short-barreled rifles and shotguns, and silencers."),
    ("1935-07-05", "law", "National Labor Relations Act", "Protects workers' right to form unions and bargain."),
    ("1935-08-14", "law", "Social Security Act", "Creates old-age pensions and unemployment insurance."),
    ("1944-06-22", "law", "G.I. Bill", "Pays for college, training and home loans for returning veterans."),
    ("1956-06-29", "law", "Federal-Aid Highway Act", "Funds the interstate highway system."),
    ("1964-07-02", "law", "Civil Rights Act of 1964", "Bans discrimination by race, color, religion, sex or national origin in jobs and public places."),
    ("1965-08-06", "law", "Voting Rights Act", "Outlaws literacy tests and other barriers that kept citizens from voting."),
    ("1968-10-22", "law", "Gun Control Act of 1968", "Licenses gun dealers and sets federal rules for who may buy firearms."),
    ("1970-12-31", "law", "Clean Air Act of 1970", "Sets national limits on air pollution."),
    ("1981-08-13", "law", "Economic Recovery Tax Act", "Reagan's across-the-board cut in income tax rates."),
    ("1986-05-19", "law", "Firearm Owners Protection Act", "Protects lawful gun owners traveling between states and bans new machine guns for civilians."),
    ("1986-10-22", "law", "Tax Reform Act of 1986", "Simplifies the income tax with fewer brackets and lower top rates."),
    ("1990-07-26", "law", "Americans with Disabilities Act", "Bans discrimination against people with disabilities in jobs, public services and public places."),
    ("1993-11-30", "law", "Brady Act", "Requires background checks for handgun purchases from licensed dealers."),
    # the Supreme Court
    ("1803-02-24", "case", "Marbury v. Madison", "The Court can strike down a law that conflicts with the Constitution (judicial review)."),
    ("1819-03-06", "case", "McCulloch v. Maryland", "Congress may create a national bank, and a state cannot tax it."),
    ("1824-03-02", "case", "Gibbons v. Ogden", "Congress, not the states, regulates trade between states."),
    ("1832-03-03", "case", "Worcester v. Georgia", "Georgia's laws had no force on Cherokee land; President Jackson did not enforce the ruling."),
    ("1833-02-16", "case", "Barron v. Baltimore", "The Bill of Rights limits only the federal government, not the states."),
    ("1857-03-06", "case", "Dred Scott v. Sandford", "The Court rules that Black Americans cannot be citizens; the 14th Amendment later overturned it."),
    ("1873-04-14", "case", "Slaughter-House Cases", "Reads the 14th Amendment's privileges or immunities clause narrowly."),
    ("1876-03-27", "case", "United States v. Cruikshank", "The First and Second Amendments are held to restrain only the federal government."),
    ("1896-05-18", "case", "Plessy v. Ferguson", "Upholds 'separate but equal' segregation; overturned in 1954."),
    ("1919-03-03", "case", "Schenck v. United States", "Speech that creates a 'clear and present danger' can be punished."),
    ("1925-06-08", "case", "Gitlow v. New York", "Free speech applies against the states through the 14th Amendment — incorporation begins."),
    ("1939-05-15", "case", "United States v. Miller", "Upholds the National Firearms Act as applied to a short-barreled shotgun."),
    ("1954-05-17", "case", "Brown v. Board of Education", "Racial segregation in public schools is unconstitutional."),
    ("1963-03-18", "case", "Gideon v. Wainwright", "States must provide a lawyer to defendants who cannot afford one."),
    ("1966-06-13", "case", "Miranda v. Arizona", "Police must tell suspects of their rights before questioning."),
    ("1969-02-24", "case", "Tinker v. Des Moines", "Students keep free-speech rights at school."),
    ("1995-04-26", "case", "United States v. Lopez", "Congress's power over interstate commerce has limits."),
    ("2008-06-26", "case", "District of Columbia v. Heller", "The Second Amendment protects an individual right to keep and bear arms."),
    ("2010-06-28", "case", "McDonald v. City of Chicago", "The Second Amendment applies to the states through the 14th Amendment."),
    ("2022-06-23", "case", "New York State Rifle & Pistol Assn. v. Bruen", "Gun laws must fit the nation's historical tradition of firearm regulation."),
    ("2024-06-21", "case", "United States v. Rahimi", "Upholds disarming people under domestic-violence restraining orders, applying Bruen's history test."),
]

# ---- the first thread (Alexandria's guided tour), from the Hivemind: "The Covenant Republic" and "The Piedmont Patriot Network"
THREAD = {
    "id": "covenant-republic",
    "title": "The Covenant Republic",
    "subtitle": "From Knox to the Piedmont presidents, and on to Reagan",
    "scribes": "Chad Peters & Claude",
    "about": "A guided thread through faith, law and self-government: how Scottish Reformation ideas about rulers under the law "
             "crossed the Atlantic with the Scots-Irish, took root in the Carolina Piedmont, shaped the demand for a bill of rights, "
             "and ran on through the Jacksonian and Reagan eras. It is a point of view, and every station links to the primary sources.",
    "stations": [
        ("1560", "John Knox and the Scottish Reformation", "John Knox (c. 1514–1572) led the Reformation in Scotland. The Presbyterian church he helped build was governed by elected elders, and he argued that the people may resist rulers who break God's law.", {"articles": ["protestant-reformation"]}),
        ("1644", "Lex Rex", "Samuel Rutherford's Lex Rex — 'the law is king' — argues that kings are under the law, not above it.", {}),
        ("1689", "English Bill of Rights", "Parliament declares that Protestant subjects 'may have arms for their defence suitable to their conditions and as allowed by law.' American courts still cite it.", {}),
        ("1740", "The Great Wagon Road", "Scots-Irish families from Ulster land in Pennsylvania and move south down the Great Wagon Road into the Carolina Piedmont — Davidsons, Polks, Grahams, Alexanders, Brevards and others.", {}),
        ("1758", "Alexander Craighead at Sugar Creek", "The Presbyterian preacher Alexander Craighead settles in Mecklenburg and teaches that rulers who break covenant with the people lose their claim on obedience.", {}),
        ("1768", "John Witherspoon comes to Princeton", "The Scottish minister Witherspoon leads the College of New Jersey, teaches James Madison and many Carolina students, and later signs the Declaration of Independence.", {}),
        ("1775-05-31", "Mecklenburg Resolves", "Mecklenburg's leaders, with Ephraim Brevard as their writer, declare the King's commissions void. (A 'Mecklenburg Declaration' dated May 20 is told in tradition; historians dispute it. The May 31 Resolves are documented.)", {"landmarks": ["Mecklenburg Resolves"]}),
        ("1781-02-01", "Cowan's Ford", "General William Lee Davidson of the North Carolina militia is killed holding the Catawba River crossing against Cornwallis. Davidson College is later named for him.", {}),
        ("1788-08-02", "Hillsborough: the great refusal", "North Carolina's convention will not ratify the Constitution without a bill of rights — one of the pressures that made Congress propose one.", {"landmarks": ["Hillsborough Convention", "North Carolina ratifies"]}),
        ("1791-12-15", "The Bill of Rights", "Ten amendments are ratified, including the rights of conscience and of the people to keep and bear arms.", {"landmarks": ["Bill of Rights (Amendments 1–10)"], "articles": ["bill-of-rights"]}),
        ("1829", "Jacksonian democracy", "Andrew Jackson, born in 1767 in the Waxhaws on the Carolina border, becomes the first president from the backcountry. His era widens voting for white men and fights the national bank. It is also the era of the Indian Removal Act and the Trail of Tears.", {"presidents": [7], "landmarks": ["Indian Removal Act", "Jackson's Bank veto", "Worcester v. Georgia"]}),
        ("1845", "James K. Polk of Mecklenburg", "Polk, born in 1795 in Mecklenburg County, becomes the 11th president. The country reaches the Pacific during his single term.", {"presidents": [11]}),
        ("1852", "William A. Graham", "General Joseph Graham's son serves as Secretary of the Navy and runs for vice president on the Whig ticket.", {}),
        ("1833-02-16", "Does the Bill of Rights bind the states?", "In Barron v. Baltimore the Court says no — the Bill of Rights restrains only the federal government. The question runs through the next two centuries.", {"landmarks": ["Barron v. Baltimore"]}),
        ("1868-07-09", "The 14th Amendment", "No state may abridge the privileges or immunities of citizens or deny due process. Its meaning for the Bill of Rights is fought over for a century and a half.", {"landmarks": ["14th Amendment", "United States v. Cruikshank", "Gitlow v. New York"]}),
        ("1981-01-20", "Reagan", "Ronald Reagan's first inaugural: 'government is not the solution to our problem; government is the problem.' His presidency turns the country back toward its founding arguments about limited government.", {"presidents": [40], "landmarks": ["Economic Recovery Tax Act", "Tax Reform Act of 1986"]}),
        ("2010-06-28", "Incorporation reaches the Second Amendment", "McDonald v. City of Chicago holds that the right to keep and bear arms binds the states.", {"landmarks": ["District of Columbia v. Heller", "McDonald v. City of Chicago"]}),
        ("2022-06-23", "Bruen: history as the test", "The Court asks whether a gun law fits the nation's historical tradition — putting the founding generation's lives and laws back at the center.", {"landmarks": ["New York State Rifle & Pistol Assn. v. Bruen", "United States v. Rahimi"]}),
    ],
}


def congress_years(n: int) -> tuple[int, int]:
    """The nth Congress: 1st 1789–1791 … 119th 2025–2027."""
    start = 1789 + 2 * (n - 1)
    return start, start + 2


def congress_for(date: str) -> int | None:
    y, m, d = (date.split("-") + ["01", "01"])[:3]
    y, md = int(y), (int(m), int(d))
    if y < 1789 or (y == 1789 and md < (3, 4)):
        return None
    start_md = (3, 4) if y < 1935 else (1, 3)       # 20th Amendment: from 1935 Congresses begin January 3
    n = (y - 1789) // 2 + 1
    if (y - 1789) % 2 == 0 and md < start_md:
        n -= 1
    return n
