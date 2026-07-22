import { useState } from 'react'
import './App.css'
import { Route, Routes } from 'react-router-dom'
import { ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import Home from './pages/Home'
import StockManagement from './pages/StockManagement'
import Test from './pages/Test'


function App() {
  return (

    <>

      <Routes>
        <Route path='/' element={<Home />} />
        <Route path='/stock' element={<StockManagement />} />
        <Route path='/test' element={<Test />} />
      </Routes>
      <ToastContainer />

    </>
  )
}

export default App
