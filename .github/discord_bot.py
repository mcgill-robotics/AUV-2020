# bot.py
import os
import sys

import discord
import argparse
import requests
import openai

parser = argparse.ArgumentParser()
parser.add_argument("issue_number")
args = parser.parse_args()
num = int(args.issue_number)

response = requests.get(f"https://api.github.com/repos/mcgill-robotics/AUV-2024/issues/{num}")
json = response.json()
title = json["title"]
names = [assignee['login'] for assignee in json["assignees"]]

names_string = names[0]
for name in names[1:-1]:
    names_string += ", " + name
if len(names) > 1:
    names_string += " and " + names[-1]


# message = "Hey Clarke here. Big thanks to " + names_string \
#     + " for closing issue " + str(json["number"]) + " - " + title + ". I really appreciate your hard work!"


DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
openai.api_key = os.getenv("CHAT_GPT_TOKEN")

def chat_with_chatgpt(prompt, model="gpt-3.5-turbo"):
    response = openai.Completion.create(
        engine=model,
        prompt=prompt,
        max_tokens=300,
        n=1,
        stop=None,
        temperature=0.5,
    )

    message = response.choices[0].text.strip()
    return message

prompt = f"You are a discord bot for autonomous underwater vehicle(AUV) projet for McGill robotics, an undergraduate student\
    design team. As a discord bot you pretend to be the robot, \"Clarke\". You job is to give kudos to a member who just closed an\
    issue on github. You are given the issue number and the title of the issue. You are also given the names of the assignees.\
    The names are {names}, the issue number is {num} and the title is {title}. Your message should be funny and end with a pun\
    that is on topic with the issue, underwater robotics, or robotics in general, and should be a positive message."


message = chat_with_chatgpt(prompt)

intents = discord.Intents.default()
client = discord.Client(intents=intents)


@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord!')
    await send_message()


async def send_message():
    for guild in client.guilds:
        if guild.name == "McGill Robotics":
            for channel in guild.channels:
                if channel.name == "discord-support":
                    await channel.send(message)
                    sys.exit(0)



client.run(DISCORD_TOKEN)