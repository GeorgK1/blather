import os
import discord
import requests
import openai

from enum import Enum
from dotenv import load_dotenv
from discord.ext import commands

load_dotenv()
TOKEN = os.environ["TOKEN"]
OPENAI_TOKEN = os.environ["OPENAI_TOKEN"]
PRESET_PATH = './presets'
ADMIN_ROLE = 'ad'


class GPTRole(Enum):
    SYSTEM = "system"
    USER = "user"


class GPTModel(Enum):
    GPT3 = "gpt-3.5-turbo"
    GPT4 = "gpt4"


class GPTRule:
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content

    def __repr__(self):
        return f"{self.role}, {self.content}"

    def create_rule(self):
        return {"role": self.role, "content": self.content}


class GPTBot:
    def __init__(self, preset_name, token):
        self.preset_name = preset_name
        self.preset_path = f"{PRESET_PATH}/{self.preset_name}"
        self.model = GPTModel.GPT3.value
        self.messages = []
        openai.api_key = token

    def read_system_config(self):
        with open(f"{self.preset_path}.txt") as f:
            for line in f:
                line = line.strip()
                if len(line) > 2:
                    self.add_rule(GPTRole.SYSTEM.value, line)

    def add_rule(self, role: str, content: str):
        rule = GPTRule(role, content)
        self.messages.append(rule.create_rule())

    def remove_rule(self):
        self.messages.pop()

    def generate_response(self, question: str):
        self.add_rule(GPTRole.USER.value, question)

        try:
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=self.messages

            )
            completion = response['choices'][0]['message']['content']

            self.remove_rule()
            return completion
        except Exception as e:
            raise openai.APIError


class DiscordBot(commands.Bot):
    def __init__(self, preset_path: str, command_prefix, intents):
        super().__init__(command_prefix, intents=intents)
        self.gptBot = GPTBot(preset_path, OPENAI_TOKEN)


intents = discord.Intents.default()
intents.message_content = True
bot = DiscordBot("preset1", "./", intents)


@bot.event
async def on_ready():
    print("I am alive")


@bot.event
async def on_message(message: discord.Message):
    if message.author != message.author.bot:
        if bot.user.mentioned_in(message):
            context = await bot.get_context(message)
            await bt(context, question=message.content)
    await bot.process_commands(message)


@bot.command()
async def bt(ctx, question: str):
    bot.gptBot.read_system_config()
    try:
        completion = bot.gptBot.generate_response(question)
        print("Completion successfully done.")
        await ctx.send(completion)
    except openai.APIError:
        print("Completion failed")
        await ctx.send("No completion done")
        bot.gptBot = GPTBot(bot.gptBot.preset_name, OPENAI_TOKEN)


@bot.command()
@commands.has_role(ADMIN_ROLE)
async def switch(ctx, preset_file: str):
    bot.gptBot = GPTBot(preset_file, OPENAI_TOKEN)
    await ctx.send("Preset changed to " + preset_file)


@bot.command()
@commands.has_role(ADMIN_ROLE)
async def add(ctx, message_id):
    message_with_attachment = await ctx.fetch_message(message_id)

    try:
        url = message_with_attachment.attachments[0].url

        if url:
            r = requests.get(url, allow_redirects=True)
            file_name = r.headers['content-disposition'].split("filename=")[1]
            file_name = file_name.replace("\"", "")

            with open(f"{PRESET_PATH}/{file_name}", 'wb') as f:
                f.write(r.content)

            await ctx.send(f"{file_name} added successfully.")

    except discord.errors.NotFound:
        await ctx.send("Failed to fetch the file.")


@bot.command()
@commands.has_role(ADMIN_ROLE)
async def remove(ctx, preset_name: str):
    try:
        os.remove(f"{PRESET_PATH}/{preset_name}.txt")
        await ctx.send(f"{preset_name} successfully removed")

        await switch(ctx, "preset1")

    except OSError:
        await ctx.send(f"Unable to remove {preset_name}")


@bot.command()
async def show(ctx):
    files = [entity for entity in os.listdir(PRESET_PATH) if entity.endswith('.txt')]
    await ctx.send("\n".join(files))


@bot.command()
async def inspect(ctx, preset_name: str):
    lines = []
    with open(f"{PRESET_PATH}/{preset_name}.txt") as f:
        for line in f:
            lines.append(line)
    await ctx.send("\n".join(lines))


@bot.command()
async def model(ctx, model_name: str):
    if model_name == GPTModel.GPT3.value:
        bot.gptBot.model = GPTModel.GPT3.value
        await ctx.send("Changed model to GPT3")
    elif model_name == GPTModel.GPT4.value:
        bot.gptBot.model = GPTModel.GPT4.value
        await ctx.send("Changed model to GPT4")

@bt.error
async def maximum_context_exceeded(ctx, error):
    if isinstance(error, openai.InvalidRequestError):
        await ctx.send("I am sorry, could not get the completion this time.")


@switch.error
@add.error
@remove.error
async def no_admin_role_error(ctx, error):
    if isinstance(error, commands.MissingRole):
        await ctx.send(f"Invalid permissions. Need {ADMIN_ROLE} role")


bot.run(TOKEN)
