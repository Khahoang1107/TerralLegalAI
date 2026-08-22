import React from 'react';
import { renderToString } from 'react-dom/server';
import UsersView from './components/admin/UsersView';
console.log(renderToString(<UsersView />));
