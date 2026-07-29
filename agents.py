from langchain.agents import create_agent
from langchain_mistralai import ChatMistralAI 
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from tools import web_search,scrape_url
import os 
from dotenv import load_dotenv
load_dotenv()

#model setup
llm = ChatMistralAI(
    model="mistral-small-latest",        # or "mistral-large-latest"
    api_key=os.getenv("MISTRAL_API_KEY"),
    temperature=0.7
)

#1st agent
def build_search_agent():
    return create_agent(
        model = llm,
        tools = [web_search]
    )

#2nd agent
def build_reader_agent():
    return create_agent(
        model=llm,
        tools = [scrape_url]
    )    

## writer chain
writer_prompt = ChatPromptTemplate.from_messages([
    ('system', '''You are a world-class research writer. 
    You will be given a topic, search results, and scraped text.
    Your goal is to write a clear, well-structured, and engaging article on the topic.
    
    - Use the search results for fresh information.
    - Use the scraped text for detailed insights.
    - Write 500-800 words.
    - Be engaging and professional.
    '''),
    ('human', ''' write a detailed research report on the topic below.
    Topic: {topic}
    Research Gathered:
    {research}
    structure the report as:
    -Introduction
    -Key Findings (minimun 3 well-explained points)
    -Conclusion
    -Sources (list all URLs found in the research)
    Be detailed, factual and professional. 
   
    '''),
    ])
writer_chain = writer_prompt | llm | StrOutputParser()


#critic_chain
critic_prompt = ChatPromptTemplate.from_messages([
    ('system', '''You are a strict and critical editor. 
    Your job is to review the research report and find any flaws, weak areas, or missing information.
    '''),
    ('human', '''
    Please review this research report and evaluate it strictly.
    Report:
    {report}

    Critique it based on:
    1. Clarity and organization
    2. Accuracy and depth of research
    3.Completeness (Are there missing points?)
    4. Engagement

    Respond in this exact format:
    score: x/10
    strengths:
    - ....
    -....
    Areas to improve:
    -...
    -...
    If you find any issues, point them out specifically.
    If the report is excellent, say so.
    '''),
    ])
critic_chain = critic_prompt | llm | StrOutputParser()
