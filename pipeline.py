from agents import build_reader_agent, build_search_agent, writer_chain, critic_chain 


def run_research_pipeline(topic: str) ->dict:
    state = {}
    # search agent working
    print("\n"+"="*50)
    print("step 1 -Search agent is working ....")
    print("="*50)
    search_agent = build_search_agent()
    search_result = search_agent.invoke({
        "messages": [("user", f"find recent, reliable and detailed information about: {topic}")]
    })

    state["research"] = search_result["messages"][-1].content

    print("\n search result ", state['research'])


    #step2 - reader agent
    print("\n"+"="*50)
    print("step 2 -Reader agent is working ....")
    print("="*50)

    reader_agent = build_reader_agent()
    reader_result = reader_agent.invoke({
        "messages": [("user",
        f"Based on the following search results about '{topic}',"
        f"pick the most relevant URL and scrape it for deeper content. \n\n"
        f"search Results: \n{state['research'][:800]}"
        )]
    })
    state['scraped_content'] = reader_result['messages'][-1].content

    print("\n Scraped content ", state['scraped_content'])

    #step 3 writer chain
    print("\n" + "=" * 50)
    print("Step 3 - Writer agent is working ....\n")
    print("=" * 50)
    
    research_combined = (
        f"Search Results : \n {state['research']} \n\n"
        f"Detailed Scraped content: \n {state['scraped_content']}" 
    )

    state['report'] = writer_chain.invoke({
        "topic": topic,
        "research" : research_combined
    })

    print("\n Final Report \n", state['report'])

    # critic report
    print("\n" + "=" * 50)
    print("Step 4 - Critic agent is working ....")
    print("=" * 50)
      
    state['feedback'] = critic_chain.invoke({
        "report" : state['report']
    }) 

    print("\n Feedback \n", state['feedback'])
    return state


if __name__ == "__main__":
    topic=input("\n Enter a research topic : ")
    run_research_pipeline(topic)