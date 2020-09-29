import json
import asyncio
import asyncpg
import re
from time import time
from datetime import datetime
from typing import Optional

import aiogram.utils.markdown as md
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.redis import RedisStorage2
# from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ParseMode, ContentType
from aiogram.utils import executor
from aiogram.types import ReplyKeyboardRemove, \
	ReplyKeyboardMarkup, KeyboardButton, \
	InlineKeyboardMarkup, InlineKeyboardButton

from config import TOKEN as API_TOKEN
from config import DATEBASE_CONF
from BASE_DICT import BASE_DICT
from cities import cities

RETURNING = '« Вернуться назад'
RETURN_TO_MM = 'Вернуться в Главное меню'
FINDING = 'Подобрать направление'

loop = asyncio.get_event_loop()

bot = Bot(token=API_TOKEN, loop=loop)

storage = RedisStorage2(db=5)

dp = Dispatcher(bot, storage=storage)

# States
class States(StatesGroup):
	# Will be represented in storage as 'States:root_buttons'
	root_buttons = State()

	# Всё, что связано с инфой о факультетах и направлениях
	faculty_selected = State()
	matching = State()
	matching_deadend = State()
	direction_selected = State()
	direction_deadend = State()

	# Всё, что связано с подачей заявления
	application_selected = State()

	i_need_hostel = State()

	name = State(),
	username = State(),
	chat_id = State(),
	date_of_birth = State(),
	gender = State(),
	passport_series = State(),
	passport_number = State(),
	country = State(),
	district = State(),
	city = State(),
	zip_code = State(),
	street = State(),
	building_number = State(),
	apartment_number = State(),
	citizenship = State(),
	phone = State(),
	email = State(),
	files = State(),
	approved = State(),
	reviewed = State(),
	direction = State(),
	exam_inf = State(),
	exam_mat = State(),
	exam_phy = State(),
	exam_rus = State(),
	exam_soc = State(),
	form = State(),
	certificate_date = State(),
	certificate_number = State(),
	certificate_series = State(),
	additional_information = State(),
	code_of_dept = State(),
	house_number = State(),
	subject = State(),
	when_issued = State(),
	who_issued = State(),

	# Общая информация
	general_information = State()

	# Сроки приёма
	reception_deadlines = State()

	# Ход приёмки
	reception_company = State()

	# Инфа о общежитии
	hostel_information = State()


@dp.message_handler(commands=['start'], state='*')
async def cmd_start(message: types.Message):
	"""
	Conversation's entry point
	Обрабатываем старт | выводит первую кнопочную развилку
	"""
	if message.text == RETURNING:
		pass

	# Creating a keyboard
	kb = ReplyKeyboardMarkup()

	for button_name in BASE_DICT:
		kb.row(KeyboardButton(button_name))

	# Set state
	await States.root_buttons.set()

	# Send message with keyboard
	await bot.send_message(
		message.chat.id,
		'Это главное меню бота, выберите интересующий вас пункт:',
		reply_markup=kb
	)


@dp.message_handler(commands=['help'], state='*')
async def cmd_help(message: types.Message):
	"""
	Help command
	"""
	await bot.send_message(
		message.chat.id,
		md.text(
			'Справка по данному боту:',
			md.text('/start', md.bold('- запустить или перезапустить бота')),
			md.text('/help', md.bold('- справочная информация о командах')),
			sep='\n'
		),
		parse_mode=ParseMode.MARKDOWN
	)


@dp.message_handler(lambda message: message.text == RETURNING,
	content_types=ContentType.TEXT, state='*')
@dp.message_handler(lambda message: message.text == RETURN_TO_MM,
	content_types=ContentType.TEXT, state='*')
async def go_back(message: types.Message, state: FSMContext):
	"""
	Go back
	Обрабатываем кнопку возврата
	"""
	current_state = str(await state.get_state())[7:]
	async with state.proxy() as data:
		if current_state == 'direction_deadend' and \
		message.text == RETURNING:
			message.text = data['faculty_selected']
			await States.faculty_selected.set()
			await faculty_selected(message, state)

		elif current_state == 'direction_deadend' and \
		message.text == RETURN_TO_MM:
			message.text = data['root_buttons']
			await cmd_start(message)

		elif current_state == 'direction_selected':
			message.text = data['root_buttons']
			await States.root_buttons.set()
			await root_buttons(message, state)

		elif current_state == 'matching':
			message.text = data['root_buttons']
			await States.root_buttons.set()
			await root_buttons(message, state)

		elif current_state == 'matching_deadend' and \
		message.text == RETURNING:
			message.text = data['root_buttons']
			await States.root_buttons.set()
			await root_buttons(message, state)

		elif current_state == 'matching_deadend' and \
		message.text == RETURN_TO_MM:
			message.text = data['root_buttons']
			await cmd_start(message)

		elif current_state == 'faculty_selected' or \
		current_state == 'application_selected' or \
		current_state == 'general_information' or \
		current_state == 'reception_deadlines' or \
		current_state == 'reception_company' or \
		current_state == 'hostel_information':
			await cmd_start(message)

		elif current_state == 'name':
			message.text = 'Подать заявление'
			await States.root_buttons.set()
			await root_buttons(message, state)
			
		elif current_state == 'gender':
			message.text = 'Я согласен на обработку персональных данных'
			await States.application_selected.set()
			await application_selected(message, state)

		elif current_state == 'date_of_birth':
			message.text = data['name']
			await States.name.set()
			await application_selected(message, state)

		elif current_state == 'city':
			message.text = data['gender']
			await States.gender.set()
			await application_selected(message, state)
						
		elif current_state == 'i_need_hostel':
			message.text = data['date_of_birth']
			await States.date_of_birth.set()
			await application_selected(message, state)

		else:
			await bot.send_message(message.chat.id,
				text='GB: Произошла какая-то ошибка! \
Напишите разработчику об этом и приложите скрины переписки с ботом')


@dp.message_handler(content_types=ContentType.TEXT, state=States.root_buttons)
async def root_buttons(message: types.Message, state: FSMContext):
	"""
	Handling of the first button fork
	Обрабатываем первую кнопочную развилку | выводит факультеты
	"""
	if message.text in BASE_DICT:
		kb = ReplyKeyboardMarkup(resize_keyboard=True)
		if BASE_DICT[message.text]['buttons']:
			for button_name in BASE_DICT[message.text]['buttons']:
				kb.row(KeyboardButton(button_name))

		kb.row(KeyboardButton(RETURNING))

		async with state.proxy() as data:
			data['root_buttons'] = message.text

		# set faculty state
		if message.text == 'Информация о факультетах':
			await States.faculty_selected.set()

		elif message.text == 'Подать заявление':
			await States.application_selected.set()

		elif message.text == 'Общие сведения':
			await States.general_information.set()
			await general_information(message, state)

		elif message.text == 'Сроки проведения приёма':
			await States.reception_deadlines.set()
			await reception_deadlines(message, state)

		elif message.text == 'Ход приёмной компании':
			await States.reception_company.set()

		elif message.text == 'Информация об общежитии':
			await States.hostel_information.set()

		await bot.send_message(message.chat.id,
			BASE_DICT[message.text]['message'],
			reply_markup=kb,
			parse_mode=ParseMode.MARKDOWN)
	else:
		await bot.send_message(message.chat.id,
			text='RBS: Произошла какая-то ошибка! \
Напишите разработчику об этом и приложите скрины переписки с ботом')
	current_state = str(await state.get_state())[7:]
	print('CURRENT STATE: ' + current_state)


@dp.message_handler(state=States.general_information)
async def general_information(message: types.Message, state: FSMContext):
	await bot.send_document(message.chat.id, 'ID_OF_DOC')
	await message.answer_location(latitude=51.313391, longitude=37.881264)


@dp.message_handler(state=States.reception_deadlines)
async def reception_deadlines(message: types.Message, state: FSMContext):
	await bot.send_photo(message.chat.id, 'ID_OF_DOC')


@dp.message_handler(content_types=ContentType.TEXT, state=States.faculty_selected)
async def faculty_selected(message: types.Message, state: FSMContext):
	"""
	Handling of faculty selection button fork
	Обрабатываем кнопочную развилку выбора факультетов (подбора) |
	выводит направления (или просьбу отослать предметы)
	"""
	async with state.proxy() as data:
		# обработка "Подборки направлений обучения"
		if message.text == FINDING:
			await States.matching.set()

			kb = ReplyKeyboardMarkup(resize_keyboard=True)
			kb.row(KeyboardButton(RETURNING))

			await bot.send_message(
				message.chat.id,
				BASE_DICT[data['root_buttons']]['buttons'][FINDING]['message'],
				reply_markup=kb,
				parse_mode=ParseMode.MARKDOWN
			)
		else:
			# обработка выбранного факультета и его направлений
			if message.text in BASE_DICT[data['root_buttons']]['buttons']:
				data['faculty_selected'] = message.text

				faculty_dict = BASE_DICT[data['root_buttons']]['buttons'] \
						[data['faculty_selected']]

				kb = ReplyKeyboardMarkup(resize_keyboard=True)
				for button_name in faculty_dict['directions']:
					kb.row(KeyboardButton(button_name))

				kb.row(KeyboardButton(RETURNING))

				# set direction state
				await States.direction_selected.set()

				await bot.send_message(message.chat.id,
					md.text(
						md.bold(faculty_dict['full_name']),
						faculty_dict['descr'],
						sep='\n'),
					reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
			else:
				await bot.send_message(message.chat.id,
					text='FS: Произошла какая-то ошибка! \
Напишите разработчику об этом и приложите скрины переписки с ботом')

@dp.message_handler(content_types=ContentType.TEXT, state=States.matching)
@dp.message_handler(content_types=ContentType.TEXT, state=States.matching_deadend)
async def matching(message: types.Message, state: FSMContext):
	"""
	Handling of matching
	Обрабатываем подбор направлений | выводит совпавшие направления
	"""
	try:
		array_of_numbers = [int(x) for x in message.text.split(' ')]

		if all(number > 0 and number < 4 for number in array_of_numbers):
			async with state.proxy() as data:
				result_text = ''
				for subject, directions in BASE_DICT[data['root_buttons']]['buttons'] \
						[FINDING]['directions'].items():
					if subject in array_of_numbers:
						result_text += directions

				kb = ReplyKeyboardMarkup(resize_keyboard=True)
				kb.row(KeyboardButton(RETURNING))
				kb.row(KeyboardButton(RETURN_TO_MM))

				await States.matching_deadend.set()

				await bot.send_message(
					message.chat.id,
					result_text,
					reply_markup=kb,
					parse_mode=ParseMode.MARKDOWN
				)

		else:
			kb = ReplyKeyboardMarkup(resize_keyboard=True)
			kb.row(KeyboardButton(RETURNING))

			await bot.send_message(
				message.chat.id,
				text='M: Неверно введены числовые обозначения предметов!',
				reply_markup=kb
			)
	except Exception as e:
		kb = ReplyKeyboardMarkup(resize_keyboard=True)
		kb.row(KeyboardButton(RETURNING))

		await bot.send_message(
			message.chat.id,
			text='M: Произошла какая-то ошибка! \
Напишите разработчику об этом и приложите скрины переписки с ботом',
			reply_markup=kb
		)

	


@dp.message_handler(content_types=ContentType.TEXT, state=States.direction_selected)
async def direction_selected(message: types.Message, state: FSMContext):
	"""
	Handling of direction selection button fork
	Обрабатываем кнопочную развилку выбора направлений | выводит инфу по направлению
	"""
	async with state.proxy() as data:		
		if message.text in BASE_DICT[data['root_buttons']] \
					['buttons'][data['faculty_selected']]['directions']:
			data['direction_selected'] = message.text

			direction_dict = BASE_DICT[data['root_buttons']] \
					['buttons'][data['faculty_selected']]['directions'] \
					[data['direction_selected']]

			ikb = InlineKeyboardMarkup()
			ikb.row(InlineKeyboardButton('Подробнее...',
				url=direction_dict['more_button_url']))

			# set direction deadend state
			await States.direction_deadend.set()

			await bot.send_message(message.chat.id,
				md.text(
					md.bold(data['direction_selected']),
					direction_dict['descr'],
					sep='\n'),
				reply_markup=ikb, parse_mode=ParseMode.MARKDOWN)

			kb = ReplyKeyboardMarkup(resize_keyboard=True)
			kb.row(KeyboardButton(RETURNING))
			kb.row(KeyboardButton('Вернуться в Главное меню'))

			await bot.send_message(message.chat.id,
				'Нажмите "Вернуться назад", чтобы вернуться к предыдущему пункту',
				reply_markup=kb)
		else:
			await bot.send_message(message.chat.id,
				text='DS: Произошла какая-то ошибка!\
				Напишите разработчику об этом и приложите скрины переписки с ботом')


#Блок обработки подачи заяления
@dp.message_handler(content_types=ContentType.TEXT, state=States.application_selected)
@dp.message_handler(content_types=ContentType.TEXT, state=States.name)
@dp.message_handler(lambda message: message.text == 'Мужской' or message.text == 'Женский',
		content_types=ContentType.TEXT, state=States.gender)
@dp.message_handler(content_types=ContentType.TEXT, state=States.date_of_birth)
@dp.message_handler(content_types=ContentType.TEXT, state=States.city)
@dp.message_handler(lambda message: message.text == 'Да' or message.text == 'Нет',
		content_types=ContentType.TEXT, state=States.i_need_hostel)
async def application_selected(message: types.Message, state: FSMContext):
	"""
	Обрабатываем подачу заявления
	"""
	async with state.proxy() as data:
		current_state = str(await state.get_state())[7:]
		print('AP_CURRENT STATE: ' + current_state)
		kb = ReplyKeyboardMarkup(resize_keyboard=True)
		result_text = ''

		if (current_state == 'application_selected' and
			message.text == 'Я согласен на обработку персональных данных'):
			await States.name.set()
			result_text = 'Отправьте ФИО через пробел\n(Например: Иванов Иван Иванович)'

		elif (current_state == 'name'):
			await States.gender.set()
			data['name'] = message.text
			result_text = 'Выберите ваш пол'
			kb.add(KeyboardButton('Мужской')).add(KeyboardButton('Женский'))

		elif (current_state == 'gender'):
			await States.date_of_birth.set()
			data['gender'] = message.text
			result_text = 'Введите дату рождения\n(Например: 01.02.2001)'

		elif (current_state == 'date_of_birth'):
			if re.match(r'\d{2}\.\d{2}\.\d{4}', message.text):
				try:
					min_date = datetime(1999, 1, 1)
					max_date = datetime(2003, 1, 1)
					current = datetime.strptime(message.text, '%d.%m.%Y')

					if min_date < current < max_date:
						await States.city.set()
						data['date_of_birth'] = message.text
						result_text = 'Введите город рождения\n(Например: Старый Оскол)'
					else:
						result_text = 'Введена неподходящая дата!\nПопробуйте еще раз.'
				except ValueError:
					result_text = 'Дата введена неверно!\nПопробуйте еще раз.'
			else:
				result_text = 'Неверный формат даты!\nПопробуйте еще раз.'

		elif (current_state == 'city'):
			if message.text in cities:
				await States.i_need_hostel.set()
				data['city'] = message.text
				result_text = 'Нужно ли предоставлять вам место в общежитии?'
				kb.add(KeyboardButton('Да')).add(KeyboardButton('Нет'))
			else:
				result_text = 'Город введен неверно!\nПопробуйте еще раз.'

		elif (current_state == 'i_need_hostel'):
			conn = await asyncpg.connect(**DATEBASE_CONF)
			# тестовая запись в БД
			values = await conn.fetch('''
				INSERT INTO user_user (id,		name,	username,			chat_id,	date_of_birth,	gender,		passport_series,	passport_number,	country,	district,				city,			zip_code,	street,					building_number,	apartment_number,	citizenship,	phone,			email,				files,		approved,	reviewed,	direction,	exam_inf,	exam_mat,	exam_phy,	exam_rus,	exam_soc,	form,		certificate_date,	certificate_number,	certificate_series,	additional_information,														code_of_dept,	house_number,	subject,	when_issued,	who_issued) VALUES
									  (DEFAULT,	'{}',	'mistertwister',	'{}',		'{}',			'{}',		1234,				123456,				'Россия',	'Белгородская область',	'Старый Оскол',	309512,		'микрорайон Жукова',	0,					250,				'Россия',		'+79040850773',	'Kyle@Brown.com',	'', 		false,		false,		NULL,   	NULL,   	NULL,   	NULL,   	NULL,   	NULL, 		'Бюджет',	'2019-05-14',		123,				456789,				'Все остальные данные в приложенных документах. Нужно ли общежитие: {}',	123456, 		23,				'',			'2012-05-14',	'УФМС')
				'''.format(
						data['name'],
						message.chat.id,
						data['date_of_birth'],
						data['gender'],
						data['i_need_hostel']
					)
			)
			print(values)
			await conn.close()

			data['i_need_hostel'] = message.text
			result_text = md.text(
				'Заявление успешно подано!',
				'ФИО: ' + data['name'],
				'Пол: ' + data['gender'],
				'Дата рождения: ' + data['date_of_birth'],
				'Место рождения: ' + data['city'],
				'Необходимо ли общежитие: ' + data['i_need_hostel'],
				sep='\n'
			)

		if current_state == 'i_need_hostel':
			kb = None
		else:
			kb.row(KeyboardButton(RETURNING))

		await bot.send_message(
			message.chat.id,
			result_text,
			reply_markup=kb,
			parse_mode=ParseMode.MARKDOWN
		)

		if current_state == 'i_need_hostel':
			await cmd_start(message)


# Обработчики неправильных сообщений и команд
@dp.message_handler()
async def echo_message(msg: types.Message):
	await bot.send_message(msg.from_user.id, "Изините, но ваши команды не удалось обработать!")


@dp.message_handler(content_types=ContentType.ANY)
async def unknown_message(message: types.Message):
	message_text = md.text(
			md.text('Я не знаю, что с этим сообщением...'),
			md.text('Просто введи', md.code('/help'), 'и ты увидишь все доступные команды!'),
			sep='\n')
	await message.reply(message_text, parse_mode=ParseMode.MARKDOWN)

if __name__ == '__main__':
	executor.start_polling(dp, loop=loop, skip_updates=True)
